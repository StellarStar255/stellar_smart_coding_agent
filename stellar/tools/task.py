"""子 agent（类似 Claude Code 的 Task / sub-agent）。

把一个独立的子任务交给一个全新的 agent 实例去完成：它有自己的对话历史
和工具集，跑完后只把「最终结论」返回给主 agent。
好处：探索性的搜索/分析不会污染主对话的上下文。
"""

from __future__ import annotations

from typing import Any

from .base import Tool, ToolContext, ToolOutput


class TaskTool(Tool):
    name = "task"
    description = (
        "启动一个子 agent 去自主完成一个明确、独立的子任务（如「在代码库里"
        "找出所有用到 X 的地方并总结」）。子 agent 有自己的上下文和工具，"
        "只返回最终结论。适合需要大量探索、但你只关心结果的场景。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "子任务的简短标题"},
            "prompt": {
                "type": "string",
                "description": "给子 agent 的完整任务说明（它看不到主对话历史，要写清楚）",
            },
        },
        "required": ["description", "prompt"],
    }

    def preview(self, args: dict[str, Any]) -> str:
        return f"启动子 agent: {args.get('description')}"

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        # 通过 extras 拿到主程序注入的「子 agent 工厂」，避免循环 import
        factory = ctx.extras.get("subagent_factory")
        if factory is None:
            return ToolOutput("子 agent 不可用（未注入工厂）。", is_error=True)
        try:
            result = factory(args["prompt"])
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"子 agent 执行失败: {e}", is_error=True)
        return ToolOutput(result)
