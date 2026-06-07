"""读取文件内容（带行号，类似 Claude Code 的 Read）。"""

from __future__ import annotations

import os
from typing import Any

from .base import Tool, ToolContext, ToolOutput

MAX_LINES = 2000
MAX_LINE_LEN = 2000


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "读取文本文件内容，返回带行号的结果（格式 `行号\\t内容`）。"
        "支持 offset/limit 读取大文件的某一段。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径（相对或绝对）"},
            "offset": {"type": "integer", "description": "起始行（从 1 开始），可选"},
            "limit": {"type": "integer", "description": "读取行数，可选"},
        },
        "required": ["path"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        path = os.path.join(ctx.workdir, args["path"])
        if not os.path.exists(path):
            return ToolOutput(f"文件不存在: {path}", is_error=True)
        if os.path.isdir(path):
            return ToolOutput(f"这是一个目录，不是文件: {path}", is_error=True)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"读取失败: {e}", is_error=True)

        offset = max(1, args.get("offset", 1))
        limit = args.get("limit", MAX_LINES)
        chunk = lines[offset - 1 : offset - 1 + limit]
        if not chunk:
            return ToolOutput("(文件为空或 offset 越界)")

        out = []
        for i, line in enumerate(chunk, start=offset):
            text = line.rstrip("\n")
            if len(text) > MAX_LINE_LEN:
                text = text[:MAX_LINE_LEN] + " …(截断)"
            out.append(f"{i}\t{text}")
        return ToolOutput("\n".join(out))
