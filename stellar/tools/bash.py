"""执行 shell 命令（类似 Claude Code 的 Bash）。有副作用，需要确认。"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from .base import Tool, ToolContext, ToolOutput

MAX_OUTPUT = 30_000


class BashTool(Tool):
    name = "bash"
    description = (
        "在工作目录下执行一条 shell 命令并返回 stdout/stderr。"
        "用于构建、测试、git、文件操作等。注意这是有副作用的操作。"
        "需要 TTY 的交互式/全屏程序（curses 游戏、vim、交互式安装器等）"
        "在普通模式下会因为无终端而失败，请改用 foreground=true。"
    )
    requires_permission = True
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的 shell 命令"},
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 120（前台模式下无效）",
            },
            "foreground": {
                "type": "boolean",
                "description": (
                    "前台模式：让命令直接接管用户的终端（继承 TTY），"
                    "用于运行交互式/全屏程序。期间 REPL 暂停等待，"
                    "输出不会被捕获，无超时限制，命令退出后控制权交还。"
                ),
            },
        },
        "required": ["command"],
    }

    def preview(self, args: dict[str, Any]) -> str:
        mode = "前台执行(接管终端)" if args.get("foreground") else "执行命令"
        return f"{mode}: {args.get('command')}"

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        command = args["command"]
        timeout = args.get("timeout", 120)
        if args.get("foreground"):
            return self._run_foreground(command, ctx)
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

    def _run_foreground(self, command: str, ctx: ToolContext) -> ToolOutput:
        """前台模式：不捕获输出，把 Stellar 自己的终端（TTY）借给子进程。

        这是普通编码 agent 跑不了 curses/vim 这类全屏程序的根本原因——
        工具通常用管道捕获输出，子进程拿不到 TTY。Stellar 本身运行在
        用户终端里，所以可以选择不捕获，让子进程直接继承终端：
        REPL 在此期间阻塞，用户与程序交互，程序退出后控制权回到 REPL。
        代价是 agent 看不到任何输出，只知道退出码。
        """
        if not sys.stdin.isatty():
            return ToolOutput(
                "前台模式需要交互式终端，当前环境没有 TTY。", is_error=True
            )
        try:
            # 不设超时：交互式程序运行多久由用户决定
            proc = subprocess.run(command, shell=True, cwd=ctx.workdir)
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"执行失败: {e}", is_error=True)
        return ToolOutput(
            f"前台命令已结束，退出码 {proc.returncode}（输出未捕获）。",
            is_error=proc.returncode != 0,
        )
