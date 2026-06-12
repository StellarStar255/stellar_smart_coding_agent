"""OpenAI (及兼容端点) provider。

负责：内部 Message 列表 <-> OpenAI chat.completions 格式 的互转，
以及流式拼接 function calling 的 arguments（OpenAI 是分片传 JSON 字符串的）。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from ..messages import (
    AssistantMessage,
    Done,
    Message,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallStart,
    ToolSpec,
    Usage,
)
from .base import Provider, encode_image


class OpenAIProvider(Provider):
    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str | None = None,
        max_tokens: int = 8096,
        system_in_user: bool = False,
    ):
        from openai import OpenAI

        if not api_key:
            raise RuntimeError("缺少 OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_tokens = max_tokens
        # 某些代理（如 Claude Code 包装层）会丢弃/替换 system 消息，
        # 开启后改为把 system prompt 包进第一条 user 消息
        self.system_in_user = system_in_user

    # ---- 内部格式 -> OpenAI 格式 ----

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "user":
                if m.images:
                    # 带图片时 content 是多模态块列表，图片用 data URI 内联
                    content: list[dict[str, Any]] = []
                    for path in m.images:
                        enc = encode_image(path)
                        if enc:
                            content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{enc[0]};base64,{enc[1]}"
                                    },
                                }
                            )
                        else:
                            content.append(
                                {"type": "text", "text": f"[图片已无法读取: {path}]"}
                            )
                    if m.text:
                        content.append({"type": "text", "text": m.text})
                    out.append({"role": "user", "content": content})
                else:
                    out.append({"role": "user", "content": m.text})
            elif m.role == "assistant":
                msg: dict[str, Any] = {"role": "assistant", "content": m.text or None}
                if m.tool_calls:
                    msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in m.tool_calls
                    ]
                out.append(msg)
            elif m.role == "tool":
                # OpenAI 每个工具结果是一条独立的 role=tool 消息
                for r in m.tool_results:
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": r.tool_call_id,
                            "content": r.content,
                        }
                    )
        return out

    def _convert_tools(self, tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    @staticmethod
    def _inject_system_into_first_user(
        oai_messages: list[dict[str, Any]], system: str
    ) -> None:
        """把 system prompt 包成标签块，前置到第一条 user 消息里。

        system 消息本身仍保留（对正常端点无害）；这里是给会丢弃
        system 的代理兜底——user 消息总是会透传的。
        """
        block = f"<system-instructions>\n{system}\n</system-instructions>\n\n"
        for m in oai_messages:
            if m["role"] != "user":
                continue
            if isinstance(m["content"], list):  # 多模态消息
                m["content"] = [{"type": "text", "text": block}] + m["content"]
            else:
                m["content"] = block + (m["content"] or "")
            return

    # ---- 流式 ----

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        oai_messages = [{"role": "system", "content": system}]
        oai_messages.extend(self._convert_messages(messages))
        if self.system_in_user:
            self._inject_system_into_first_user(oai_messages, system)
        oai_tools = self._convert_tools(tools)

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            tools=oai_tools or None,
            max_tokens=self.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        text = ""
        # index -> {"id", "name", "args"}：流式拼接每个 tool_call
        acc: dict[int, dict[str, str]] = {}
        usage = Usage()

        for chunk in stream:
            if chunk.usage:
                usage = Usage(
                    chunk.usage.prompt_tokens, chunk.usage.completion_tokens
                )
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text += delta.content
                yield TextDelta(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        # 首次拿到名字时，发一个「工具开始」事件给 UI
                        if not slot["name"]:
                            yield ToolCallStart(tc.function.name)
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments

        tool_calls: list[ToolCall] = []
        for idx in sorted(acc):
            slot = acc[idx]
            try:
                args = json.loads(slot["args"]) if slot["args"].strip() else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(slot["id"], slot["name"], args))

        yield Done(AssistantMessage(text, tool_calls, usage))
