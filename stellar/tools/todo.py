"""任务清单（类似 Claude Code 的 TodoWrite）。

让模型把复杂任务拆成可勾选的步骤，状态存在 ctx.state 里，
UI 可以渲染出来。这能显著提升多步任务的可靠性。
"""

from __future__ import annotations

from typing import Any

from .base import Tool, ToolContext, ToolOutput

VALID_STATUS = {"pending", "in_progress", "completed"}


class TodoWriteTool(Tool):
    name = "todo_write"
    description = (
        "维护当前任务的待办清单。传入完整的 todo 列表（每项含 content 和 status）。"
        "用于规划和跟踪多步骤任务。每次调用会整体覆盖清单。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                    },
                    "required": ["content", "status"],
                },
            }
        },
        "required": ["todos"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        todos = args.get("todos", [])
        cleaned = []
        for t in todos:
            status = t.get("status", "pending")
            if status not in VALID_STATUS:
                status = "pending"
            cleaned.append({"content": t.get("content", ""), "status": status})
        ctx.state["todos"] = cleaned

        # 给模型一个简洁的回执
        lines = []
        marks = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
        for t in cleaned:
            lines.append(f"{marks[t['status']]} {t['content']}")
        return ToolOutput("任务清单已更新：\n" + "\n".join(lines))
