"""Agent 核心：agentic loop。

这是整个项目最重要的文件，也是 Claude Code 的本质：

    while True:
        模型基于 [system + 历史 + 工具] 生成回复（可能含 tool_calls）
        若没有 tool_calls  -> 回合结束，把控制权交还用户
        若有 tool_calls    -> 逐个执行（必要时请求确认），把结果喂回历史，继续循环

就这么简单。所谓「智能体」，就是让模型在这个循环里自己决定下一步调用什么工具。
"""

from __future__ import annotations

from .config import Config
from .history import History
from .messages import (
    AssistantMessage,
    Done,
    Message,
    TextDelta,
    ToolCallStart,
    ToolResult,
)
from .permissions import PermissionManager
from .prompts import SUBAGENT_SYSTEM_PROMPT, build_system_prompt
from .providers import Provider, build_provider
from .tools import Tool, ToolContext, default_tools
from . import ui


class Agent:
    def __init__(
        self,
        config: Config,
        provider: Provider | None = None,
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        interactive: bool = True,
        session_path: str | None = None,
    ):
        self.config = config
        self.provider = provider or build_provider(config)
        self.tools = tools if tools is not None else default_tools()
        self.tool_map = {t.name: t for t in self.tools}
        self.system_prompt = system_prompt or build_system_prompt(config.workdir)
        self.history = History()
        self.permissions = PermissionManager(yolo=config.yolo)
        self.interactive = interactive
        # 会话持久化文件路径（None 表示不持久化，如子 agent）
        self.session_path = session_path
        self.ctx = ToolContext(workdir=config.workdir)
        # 给 task 工具注入「创建子 agent」的能力
        self.ctx.extras["subagent_factory"] = self._run_subagent

    # ---------- 主循环 ----------

    def run_turn(self, user_input: str) -> None:
        """处理一次用户输入，跑完整个 agentic loop 直到不再需要工具。"""
        self.history.add_user(user_input)
        self._maybe_compact()

        while True:
            assistant_msg = self._call_model(stream_to_ui=self.interactive)
            self.history.add(
                Message(
                    role="assistant",
                    text=assistant_msg.text,
                    tool_calls=assistant_msg.tool_calls,
                )
            )

            if not assistant_msg.tool_calls:
                self._save_session()
                return  # 模型不再需要工具，回合结束

            results = self._execute_tools(assistant_msg)
            self.history.add(Message(role="tool", tool_results=results))
            self._save_session()
            # 继续循环：把工具结果喂回模型

    def _call_model(self, stream_to_ui: bool) -> AssistantMessage:
        tool_specs = [t.spec() for t in self.tools]
        if stream_to_ui:
            ui.assistant_prefix()
        final: AssistantMessage | None = None
        printed_any = False
        for event in self.provider.stream(
            self.system_prompt, self.history.messages, tool_specs
        ):
            if isinstance(event, TextDelta):
                if stream_to_ui:
                    ui.stream_text(event.text)
                    printed_any = True
            elif isinstance(event, ToolCallStart):
                if stream_to_ui:
                    ui.stream_tool_start(event.name)
                    printed_any = False  # 已换行，无需再补行
            elif isinstance(event, Done):
                final = event.message
        if stream_to_ui and printed_any:
            ui.end_line()
        assert final is not None, "provider 未产出 Done 事件"
        self.history.last_input_tokens = final.usage.input_tokens
        return final

    # ---------- 工具执行 ----------

    def _execute_tools(self, assistant_msg: AssistantMessage) -> list[ToolResult]:
        results: list[ToolResult] = []
        for tc in assistant_msg.tool_calls:
            tool = self.tool_map.get(tc.name)
            if tool is None:
                results.append(
                    ToolResult(tc.id, f"未知工具: {tc.name}", is_error=True)
                )
                continue

            preview = tool.preview(tc.arguments)
            if self.interactive:
                ui.tool_call(tc.name, preview)
                # diff 预览：写/编辑文件类工具在确认前展示改动
                diff_text = tool.diff_preview(tc.arguments, self.ctx)
                if diff_text:
                    ui.diff(diff_text)

            # 权限确认
            if tool.requires_permission and not self.permissions.is_pre_approved(
                tc.name
            ):
                if not self.interactive:
                    # 非交互（子 agent）默认放行无需确认的，拒绝需确认的
                    results.append(
                        ToolResult(
                            tc.id,
                            "（子 agent 无权执行需确认的操作，已跳过）",
                            is_error=True,
                        )
                    )
                    continue
                decision = ui.confirm(tc.name, preview)
                if decision == "n":
                    results.append(
                        ToolResult(tc.id, "用户拒绝了这次操作。", is_error=True)
                    )
                    continue
                if decision == "a":
                    self.permissions.remember(tc.name)

            # 真正执行
            try:
                out = tool.run(tc.arguments, self.ctx)
            except Exception as e:  # noqa: BLE001
                out_content, is_error = f"工具异常: {e}", True
            else:
                out_content, is_error = out.content, out.is_error

            if self.interactive:
                ui.tool_result(out_content, is_error)
                if tc.name == "todo_write":
                    ui.todos(self.ctx.state.get("todos", []))

            results.append(ToolResult(tc.id, out_content, is_error))
        return results

    # ---------- 会话持久化 ----------

    def _save_session(self) -> None:
        if not self.session_path:
            return
        try:
            self.history.save(self.session_path)
        except OSError:
            pass  # 存档失败不应中断对话

    # ---------- 历史压缩 ----------

    def _maybe_compact(self) -> None:
        if not self.history.needs_compaction(self.config.compact_threshold):
            return
        if self.interactive:
            ui.info("（上下文较长，正在压缩历史…）")
        self.history.compact(self._summarize)

    def _summarize(self, messages: list[Message]) -> str:
        """用模型把一段历史总结成文字（用于 compaction）。"""
        transcript = _render_transcript(messages)
        sub = Agent(
            self.config,
            provider=self.provider,
            tools=[],
            system_prompt="你是一个对话摘要器。",
            interactive=False,
        )
        sub.history.add_user(
            "请把下面这段编程 agent 的对话压缩成简洁但信息完整的摘要，"
            "保留：用户目标、已做的关键改动和文件、重要结论、待办事项。\n\n"
            + transcript
        )
        msg = sub._call_model(stream_to_ui=False)
        return msg.text

    # ---------- 子 agent（task 工具用）----------

    def _run_subagent(self, prompt: str) -> str:
        """创建一个全新的、非交互的子 agent 跑完任务，返回它的最终回复文本。"""
        sub = Agent(
            self.config,
            provider=self.provider,
            tools=default_tools(include_task=False),  # 不再嵌套 task
            system_prompt=SUBAGENT_SYSTEM_PROMPT,
            interactive=False,
        )
        sub.run_turn(prompt)
        # 子 agent 最后一条 assistant 消息就是它的结论
        for m in reversed(sub.history.messages):
            if m.role == "assistant" and m.text:
                return m.text
        return "(子 agent 没有产出文本结论)"


def _render_transcript(messages: list[Message]) -> str:
    parts = []
    for m in messages:
        if m.role == "user":
            parts.append(f"用户: {m.text}")
        elif m.role == "assistant":
            if m.text:
                parts.append(f"助手: {m.text}")
            for tc in m.tool_calls:
                parts.append(f"助手[调用工具 {tc.name}]: {tc.arguments}")
        elif m.role == "tool":
            for r in m.tool_results:
                snippet = r.content[:500]
                parts.append(f"工具结果: {snippet}")
    return "\n".join(parts)
