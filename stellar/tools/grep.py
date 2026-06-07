"""按正则在文件内容中搜索（类似 Claude Code 的 Grep）。优先用 ripgrep，回退到 Python。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

from .base import Tool, ToolContext, ToolOutput

MAX_MATCHES = 200


class GrepTool(Tool):
    name = "grep"
    description = "在文件内容里用正则搜索，返回匹配的 `文件:行号:内容`。可用 glob 过滤文件。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "正则表达式"},
            "path": {"type": "string", "description": "搜索目录，默认工作目录"},
            "glob": {"type": "string", "description": "文件名过滤，如 *.py，可选"},
        },
        "required": ["pattern"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        pattern = args["pattern"]
        root = os.path.normpath(os.path.join(ctx.workdir, args.get("path", ".")))
        glob = args.get("glob")

        if shutil.which("rg"):
            return self._ripgrep(pattern, root, glob)
        return self._python_grep(pattern, root, glob)

    def _ripgrep(self, pattern: str, root: str, glob: str | None) -> ToolOutput:
        cmd = ["rg", "--line-number", "--no-heading", "--color=never", pattern, root]
        if glob:
            cmd[1:1] = ["--glob", glob]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"搜索失败: {e}", is_error=True)
        lines = proc.stdout.splitlines()
        if not lines:
            return ToolOutput("(无匹配)")
        truncated = len(lines) > MAX_MATCHES
        body = "\n".join(lines[:MAX_MATCHES])
        if truncated:
            body += f"\n…(共 {len(lines)} 条，已截断)"
        return ToolOutput(body)

    def _python_grep(self, pattern: str, root: str, glob: str | None) -> ToolOutput:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return ToolOutput(f"正则错误: {e}", is_error=True)
        import fnmatch

        results: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
            for fn in filenames:
                if glob and not fnmatch.fnmatch(fn, glob):
                    continue
                fp = os.path.normpath(os.path.join(dirpath, fn))
                try:
                    with open(fp, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if rx.search(line):
                                results.append(f"{fp}:{i}:{line.rstrip()}")
                                if len(results) >= MAX_MATCHES:
                                    results.append("…(已达上限，已截断)")
                                    return ToolOutput("\n".join(results))
                except (OSError, UnicodeDecodeError):
                    continue
        return ToolOutput("\n".join(results) if results else "(无匹配)")
