"""终端 UI：流式输出、工具调用展示、权限确认提示。

用 rich 让输出更好看；没装 rich 也能降级成纯文本。
"""

from __future__ import annotations

from typing import Any

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    _console: Console | None = Console()
except ImportError:  # rich 可选
    _console = None


def _plain(*args: Any) -> None:
    print(*args)


def banner(provider: str, model: str, workdir: str) -> None:
    text = (
        f"[bold cyan]Stellar[/] 编码 agent\n"
        f"provider=[green]{provider}[/]  model=[green]{model}[/]\n"
        f"cwd={workdir}\n"
        f"[dim]输入任务开始；/help 查看命令，/exit 退出[/]"
    )
    if _console:
        _console.print(Panel(text, expand=False, border_style="cyan"))
    else:
        _plain(f"Stellar — {provider}/{model} @ {workdir}\n(/help, /exit)")


def help_text() -> None:
    lines = [
        "/help     显示帮助",
        "/exit     退出（Ctrl-D 同样）",
        "/clear    清空对话历史",
        "/compact  手动压缩历史",
        "/tokens   显示上一回合 token 用量",
        "/yolo     切换 yolo 模式（跳过所有确认）",
    ]
    if _console:
        _console.print(Panel("\n".join(lines), title="命令", border_style="dim"))
    else:
        _plain("\n".join(lines))


def assistant_prefix() -> None:
    if _console:
        _console.print("\n[bold green]●[/] ", end="")
    else:
        _plain("\n● ", end="")


def stream_text(chunk: str) -> None:
    if _console:
        _console.print(chunk, end="", soft_wrap=True, highlight=False, markup=False)
    else:
        print(chunk, end="", flush=True)


def end_line() -> None:
    if _console:
        _console.print()
    else:
        print()


def stream_tool_start(name: str) -> None:
    """流式中：模型刚决定调用某工具时的实时提示。"""
    if _console:
        _console.print(f"\n  [dim]→ 准备调用 [yellow]{name}[/yellow]…[/dim]")
    else:
        _plain(f"\n  → 准备调用 {name}…")


def tool_call(name: str, preview: str) -> None:
    if _console:
        _console.print(f"  [yellow]⚙ {name}[/] [dim]{preview}[/]")
    else:
        _plain(f"  ⚙ {name}  {preview}")


def diff(diff_text: str, max_lines: int = 40) -> None:
    """渲染彩色 unified diff。"""
    lines = diff_text.splitlines()
    truncated = len(lines) > max_lines
    lines = lines[:max_lines]
    if _console:
        out = []
        for ln in lines:
            if ln.startswith("+") and not ln.startswith("+++"):
                out.append(f"[green]{ln}[/green]")
            elif ln.startswith("-") and not ln.startswith("---"):
                out.append(f"[red]{ln}[/red]")
            elif ln.startswith("@@"):
                out.append(f"[cyan]{ln}[/cyan]")
            else:
                out.append(f"[dim]{ln}[/dim]")
        if truncated:
            out.append("[dim]…(diff 过长已截断)[/dim]")
        _console.print(Panel("\n".join(out), title="改动预览", border_style="yellow", expand=False))
    else:
        _plain("\n".join(lines) + ("\n…(已截断)" if truncated else ""))


def tool_result(content: str, is_error: bool, max_lines: int = 12) -> None:
    lines = content.splitlines()
    shown = lines[:max_lines]
    body = "\n".join(shown)
    if len(lines) > max_lines:
        body += f"\n… (+{len(lines) - max_lines} 行)"
    color = "red" if is_error else "dim"
    if _console:
        indented = "\n".join("    " + ln for ln in body.splitlines())
        _console.print(f"[{color}]{indented}[/]")
    else:
        _plain("\n".join("    " + ln for ln in body.splitlines()))


def todos(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    marks = {"pending": "○", "in_progress": "◐", "completed": "●"}
    lines = [f"{marks.get(t['status'], '○')} {t['content']}" for t in items]
    if _console:
        _console.print(Panel("\n".join(lines), title="待办", border_style="blue", expand=False))
    else:
        _plain("待办:\n" + "\n".join(lines))


def confirm(name: str, preview: str) -> str:
    """返回 'y' / 'a'(always) / 'n'。"""
    prompt = (
        f"\n[bold yellow]需要确认[/] {name}: {preview}\n"
        f"[dim]允许? (y=本次 / a=本会话总是 / n=拒绝)[/] "
    )
    if _console:
        _console.print(prompt, end="")
    else:
        _plain(f"\n需要确认 {name}: {preview}\n允许? (y/a/n) ", end="")
    try:
        ans = input().strip().lower()
    except EOFError:
        return "n"
    if ans in ("y", "yes", ""):
        return "y"
    if ans in ("a", "always"):
        return "a"
    return "n"


def info(msg: str) -> None:
    if _console:
        _console.print(f"[dim]{msg}[/]")
    else:
        _plain(msg)


def error(msg: str) -> None:
    if _console:
        _console.print(f"[red]{msg}[/]")
    else:
        _plain(msg)


def user_prompt() -> str:
    if _console:
        _console.print("\n[bold cyan]›[/] ", end="")
        return input()
    return input("\n› ")
