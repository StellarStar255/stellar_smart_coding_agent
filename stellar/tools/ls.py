"""列目录（类似 Claude Code 的 LS）。"""

from __future__ import annotations

import os
from typing import Any

from .base import Tool, ToolContext, ToolOutput


class LSTool(Tool):
    name = "ls"
    description = "列出某个目录下的文件和子目录。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认工作目录"},
        },
        "required": [],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        path = os.path.join(ctx.workdir, args.get("path", "."))
        if not os.path.isdir(path):
            return ToolOutput(f"不是目录: {path}", is_error=True)
        entries = sorted(os.listdir(path))
        lines = []
        for e in entries:
            full = os.path.join(path, e)
            lines.append(f"{e}/" if os.path.isdir(full) else e)
        return ToolOutput("\n".join(lines) if lines else "(空目录)")
