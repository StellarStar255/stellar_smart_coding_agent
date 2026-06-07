"""创建/覆盖文件（类似 Claude Code 的 Write）。有副作用，需要确认。"""

from __future__ import annotations

import os
from typing import Any

from .base import Tool, ToolContext, ToolOutput


class WriteFileTool(Tool):
    name = "write_file"
    description = "把内容写入文件（不存在则创建，存在则整体覆盖）。会自动创建父目录。"
    requires_permission = True
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "完整文件内容"},
        },
        "required": ["path", "content"],
    }

    def preview(self, args: dict[str, Any]) -> str:
        n = len(args.get("content", "").splitlines())
        return f"写入文件 {args.get('path')}  ({n} 行)"

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        path = os.path.join(ctx.workdir, args["path"])
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(args["content"])
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"写入失败: {e}", is_error=True)
        n = len(args["content"].splitlines())
        return ToolOutput(f"已写入 {path}（{n} 行）")
