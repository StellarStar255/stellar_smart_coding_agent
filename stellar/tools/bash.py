"""执行 shell 命令（类似 Claude Code 的 Bash）。有副作用，需要确认。"""

from __future__ import annotations

import subprocess
from typing import Any

from .base import Tool, ToolContext, ToolOutput

MAX_OUTPUT = 30_000


class BashTool(Tool):
    name = "bash"
    description = (
        "在工作目录下执行一条 shell 命令并返回 stdout/stderr。"
        "用于构建、测试、git、文件操作等。注意这是有副作用的操作。"
    )
    requires_permission = True
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 120",
            },
        },
        "required": ["command"],
    }

    def preview(self, args: dict[str, Any]) -> str:
        return f"执行命令: {args.get('command')}"

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        command = args["command"]
        timeout = args.get("timeout", 120)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=ctx.workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolOutput(f"命令超时（>{timeout}s）", is_error=True)
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"执行失败: {e}", is_error=True)

        out = proc.stdout + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        out = out.strip()
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n…(输出过长已截断)"
        if not out:
            out = "(无输出)"
        prefix = "" if proc.returncode == 0 else f"[退出码 {proc.returncode}]\n"
        return ToolOutput(prefix + out, is_error=proc.returncode != 0)
