"""按 glob 模式查找文件路径（类似 Claude Code 的 Glob）。"""

from __future__ import annotations

import glob as globlib
import os
from typing import Any

from .base import Tool, ToolContext, ToolOutput

MAX_RESULTS = 300


class GlobTool(Tool):
    name = "glob"
    description = "用 glob 模式查找文件，如 '**/*.py'、'src/**/*.ts'。返回匹配的文件路径列表。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "glob 模式，支持 **"},
            "path": {"type": "string", "description": "搜索根目录，默认工作目录"},
        },
        "required": ["pattern"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        root = os.path.join(ctx.workdir, args.get("path", "."))
        pattern = os.path.join(root, args["pattern"])
        matches = [
            os.path.normpath(p)
            for p in globlib.glob(pattern, recursive=True)
            if os.path.isfile(p)
        ]
        matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        if not matches:
            return ToolOutput("(无匹配文件)")
        truncated = len(matches) > MAX_RESULTS
        body = "\n".join(matches[:MAX_RESULTS])
        if truncated:
            body += f"\n…(共 {len(matches)} 个，已截断)"
        return ToolOutput(body)
