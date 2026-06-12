"""终端 UI：流式输出、工具调用展示、权限确认提示。

用 rich 让输出更好看；没装 rich 也能降级成纯文本。
"""

from __future__ import annotations

import re
import sys
from typing import Any

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    _console: Console | None = Console()
except ImportError:  # rich 可选
    _console = None


def ensure_utf8_io() -> None:
    """强制把 stdin/stdout/stderr 切到 UTF-8。

    某些终端/locale（如 C/POSIX）下，Python 默认用非 UTF-8 编码读 stdin，
    输入中文等多字节字符时 input() 会抛 UnicodeDecodeError。这里统一兜底。
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            # 流被重定向/不支持 reconfigure 时忽略
            pass


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
        "/help            显示帮助",
        "/exit            退出（Ctrl-D 同样）",
        "/clear           清空当前会话历史",
        "/compact         手动压缩历史",
        "/tokens          显示上一回合 token 用量",
        "/yolo            切换 yolo 模式（跳过所有确认）",
        "",
        "/sessions        列出所有会话",
        "/session <名字>  切换/新建到指定会话",
        "/new [名字]      开一个新会话",
        "/delete <名字>   删除某个会话",
    ]
    if _console:
        _console.print(Panel("\n".join(lines), title="命令", border_style="dim"))
    else:
        _plain("\n".join(lines))


def sessions_list(infos: list[Any], current: str | None) -> None:
    """渲染会话列表。infos 是 SessionInfo 列表。"""
    from datetime import datetime

    if not infos:
        info("（还没有任何会话）")
        return
    rows = []
    for i, s in enumerate(infos, 1):
        mark = "[green]●[/]" if s.name == current else " "
        when = datetime.fromtimestamp(s.modified).strftime("%m-%d %H:%M")
        preview = (s.preview or "").replace("\n", " ")
        if _console:
            rows.append(
                f"{mark} [bold]{s.name}[/]  [dim]{s.num_messages}条 · {when}[/]\n"
                f"    [dim]{preview}[/]"
            )
        else:
            cur = "*" if s.name == current else " "
            rows.append(f"{cur} {s.name}  {s.num_messages}条 {when}  {preview}")
    if _console:
        _console.print(Panel("\n".join(rows), title="会话列表", border_style="blue"))
    else:
        _plain("\n".join(rows))


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


# ---- 权限确认：方向键菜单（类似 Claude Code），非 TTY 降级为文本输入 ----

_CONFIRM_OPTIONS = [
    ("y", "允许（本次）"),
    ("a", "总是允许（本会话内）"),
    ("n", "拒绝"),
]


def _menu_supported() -> bool:
    """方向键菜单需要：双向都是 TTY + termios（即 Unix 终端）。"""
    try:
        import termios  # noqa: F401
    except ImportError:
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()


def _parse_key(buf: bytes) -> tuple[str | None, bytes]:
    """从字节缓冲头部解析一个按键，返回 (按键, 剩余字节)。

    方向键翻译成 'up'/'down'，其余 ESC 序列归为 'esc'。
    序列还没到齐时返回 (None, buf)，由调用方决定继续等还是按裸 Esc 处理。
    """
    if not buf:
        return None, buf
    if buf[0:1] == b"\x1b":
        if buf[1:2] == b"[":
            if len(buf) < 3:
                return None, buf
            return {b"A": "up", b"B": "down"}.get(buf[2:3], ""), buf[3:]
        if len(buf) >= 2:
            return "esc", buf[1:]
        return None, buf  # 只有一个 ESC：可能是裸 Esc 键，也可能序列未到齐
    return buf[0:1].decode("utf-8", "ignore"), buf[1:]


def _menu_select(options: list[tuple[str, str]]) -> str:
    """渲染可上下移动的选择菜单，返回选中项的 value。

    实现是终端 UI 的老把戏：打印 N 行选项，每次按键后光标上移
    N 行（ESC[NA）原地重绘。两个容易踩的坑：
    - cbreak 必须覆盖整个菜单期间。若每读一个键就恢复终端模式，
      两次按键之间到达的输入会被行规程扣住（行缓冲+回显），按键丢失。
    - 一次 os.read 可能带回多个按键（如快速的「↓ 回车」），
      所以要用缓冲逐个解析，而不是读一次取一个。
    """
    import os
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    idx = 0
    n = len(options)
    buf = b""
    w = sys.stdout

    def next_key() -> str:
        nonlocal buf
        while True:
            key, rest = _parse_key(buf)
            if key is not None:
                buf = rest
                return key
            # 缓冲为空则一直等；是半截 ESC 序列则只等 50ms，
            # 等不到后续字节就当裸 Esc 键
            timeout = 0.05 if buf else None
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                buf = b""
                return "esc"
            data = os.read(fd, 64)
            if not data:
                buf = b""
                return "esc"
            buf += data

    w.write("\x1b[?25l")  # 隐藏光标，避免重绘闪烁
    try:
        tty.setcbreak(fd)  # cbreak 保留 Ctrl-C 信号，用户仍可中断
        while True:
            for i, (_, label) in enumerate(options):
                style = "\x1b[1;36m❯ " if i == idx else "\x1b[2m  "
                w.write(f"\r\x1b[2K{style}{label}\x1b[0m\n")
            w.flush()
            key = next_key()
            if key == "up":
                idx = (idx - 1) % n
            elif key == "down":
                idx = (idx + 1) % n
            elif key in ("\r", "\n"):
                break
            elif key == "esc":
                idx = n - 1
                break
            else:
                # y/a/n 快捷键：按下即选中，兼容老习惯
                for i, (value, _) in enumerate(options):
                    if key.lower() == value:
                        idx = i
                        break
                else:
                    continue
                break
            w.write(f"\x1b[{n}A")  # 光标回到菜单顶部，下一轮重绘
        # 选完把菜单擦掉，由调用方打印一行结果，保持输出紧凑
        w.write(f"\x1b[{n}A")
        for _ in range(n):
            w.write("\x1b[2K\n")
        w.write(f"\x1b[{n}A")
        return options[idx][0]
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        w.write("\x1b[?25h")
        w.flush()


def confirm(name: str, preview: str) -> str:
    """返回 'y' / 'a'(always) / 'n'。"""
    if _console:
        _console.print(f"\n[bold yellow]需要确认[/] {name}: {preview}")
    else:
        _plain(f"\n需要确认 {name}: {preview}")

    if _menu_supported():
        if _console:
            _console.print("[dim]↑↓ 选择，Enter 确认，Esc 拒绝（或直接按 y/a/n）[/]")
        else:
            _plain("↑↓ 选择，Enter 确认，Esc 拒绝（或直接按 y/a/n）")
        choice = _menu_select(_CONFIRM_OPTIONS)
        info(f"→ {dict(_CONFIRM_OPTIONS)[choice]}")
        return choice

    # 降级：非 TTY（管道等）用原来的文本输入
    if _console:
        _console.print("[dim]允许? (y=本次 / a=本会话总是 / n=拒绝)[/] ", end="")
    else:
        _plain("允许? (y/a/n) ", end="")
    try:
        ans = _safe_input().strip().lower()
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


# CSI 转义序列（如括号粘贴标记 \x1b[200~ / 方向键 \x1b[A）
_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[~A-Za-z]")


def _sanitize_input(s: str) -> str:
    """清洗输入里的终端控制字符。

    粘贴/拖拽时，终端可能把转义序列混进 input() 读到的内容里
    （比如括号粘贴的 \\x1b[200~ 标记、或裸 ESC 字符）。这些不可见
    字符会污染消息——比如让图片路径不再以 .png 结尾而识别失败。
    """
    s = _CSI_RE.sub("", s)
    return "".join(ch for ch in s if ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127))


def _safe_input() -> str:
    """读一行输入，碰到无法解码的字节时不崩溃，提示用户重输。"""
    try:
        return _sanitize_input(input())
    except UnicodeDecodeError:
        error("（输入编码无法识别，已忽略本行，请重新输入）")
        return ""


def user_prompt() -> str:
    if _console:
        _console.print("\n[bold cyan]›[/] ", end="")
    else:
        print("\n› ", end="", flush=True)
    return _safe_input()
