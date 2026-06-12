"""memory_write 工具：让 agent 把值得长期记住的信息写进记忆文件。"""

from __future__ import annotations

from typing import Any

from .. import memory
from .base import Tool, ToolContext, ToolOutput


class MemoryWriteTool(Tool):
    name = "memory_write"
    description = (
        "把值得跨会话记住的信息写入持久记忆。"
        "scope=global 记用户本人（身份、编码习惯、通用要求），"
        "scope=project 记当前项目（约定、背景、长期任务）。"
        "mode=append 追加一条；mode=replace 用 content 整体重写该记忆文件"
        "（用于整理或删除过期记忆，重写前必须先读取原文件保留仍有效的条目）。"
        "只记长期有效的事实和偏好，不要记一次性任务细节。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["global", "project"],
                "description": "global=跨项目的用户记忆，project=当前项目记忆",
            },
            "content": {
                "type": "string",
                "description": "要记住的内容。append 时是一条简短事实；replace 时是完整的新文件内容",
            },
            "mode": {
                "type": "string",
                "enum": ["append", "replace"],
                "description": "append=追加（默认），replace=整体重写",
            },
        },
        "required": ["scope", "content"],
    }
    requires_permission = True

    def preview(self, args: dict[str, Any]) -> str:
        scope = "全局" if args.get("scope") == "global" else "项目"
        mode = "重写" if args.get("mode") == "replace" else "追加"
        content = args.get("content", "")
        if len(content) > 200:
            content = content[:200] + "…"
        return f"{mode}{scope}记忆: {content}"

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        path = memory.resolve_path(args["scope"], ctx.workdir)
        content = args["content"].strip()
        if not content:
            return ToolOutput("内容为空，未写入。", is_error=True)
        try:
            if args.get("mode") == "replace":
                memory.replace(path, content)
                return ToolOutput(f"已重写记忆文件 {path}")
            memory.append(path, content)
            return ToolOutput(f"已追加到记忆文件 {path}")
        except OSError as e:
            return ToolOutput(f"写入记忆失败: {e}", is_error=True)
