"""命令行入口 + 交互式 REPL。

用法:
    python -m stellar                          # 用 .env 里的配置
    python -m stellar --provider openai        # 临时切换 provider
    python -m stellar --model claude-opus-4-8
    python -m stellar -p "帮我写一个快排"        # 单次非交互执行
    python -m stellar --yolo                    # 跳过所有确认（慎用）
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from .agent import Agent
from .config import Config
from .sessions import SessionManager
from . import ui

LEGACY_SESSION_FILE = os.path.join(".stellar", "session.json")

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def is_command(line: str) -> bool:
    """判断输入是否是 /命令。

    不能简单用 startswith("/")：以 / 开头的还可能是文件路径
    （比如终端把粘贴的图片存盘后插入的 /Users/...png）。
    命令的形状是「/ + 纯字母」，路径里必然还有别的字符。
    """
    head = line.split(maxsplit=1)[0]
    return re.fullmatch(r"/[A-Za-z]+", head) is not None


def extract_images(text: str) -> list[str]:
    """从输入文本里找出指向真实图片文件的路径。

    终端粘贴/拖拽图片时通常会插入文件路径。按空白切分 token
    （兼容拖拽产生的「反斜杠转义空格」），凡是以图片扩展名结尾
    且文件真实存在的，就当作要发给模型的图片。
    """
    images = []
    for token in re.findall(r"(?:\\ |\S)+", text):
        token = token.strip("'\"").replace("\\ ", " ")
        if token.lower().endswith(IMAGE_EXTS):
            path = os.path.abspath(os.path.expanduser(token))
            if os.path.isfile(path):
                images.append(path)
    return images


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="stellar", description="Stellar 编码 agent")
    p.add_argument("--provider", choices=["anthropic", "openai"], help="模型 provider")
    p.add_argument("--model", help="模型名")
    p.add_argument("--workdir", default=".", help="工作目录")
    p.add_argument("--yolo", action="store_true", help="跳过所有权限确认")
    p.add_argument("-p", "--prompt", help="单次执行该提示后退出（非交互）")
    p.add_argument("-s", "--session", help="使用/新建指定名字的会话")
    p.add_argument(
        "--resume",
        nargs="?",
        const=True,
        default=False,
        metavar="NAME",
        help="恢复会话：不带名字=恢复最近的，带名字=恢复该会话",
    )
    return p.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    config = Config.from_env()
    if args.provider:
        config.provider = args.provider
        config.model = args.model or __import__(
            "stellar.config", fromlist=["DEFAULT_MODELS"]
        ).DEFAULT_MODELS.get(args.provider)
    if args.model:
        config.model = args.model
    config.workdir = args.workdir
    if args.yolo:
        config.yolo = True
    return config


def handle_command(cmd: str, agent: Agent) -> bool:
    """处理 /命令。返回 True 表示应退出。"""
    cmd = cmd.strip()
    parts = cmd.split(maxsplit=1)
    head = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if head in ("/exit", "/quit"):
        agent._save_session()
        return True
    if head == "/help":
        ui.help_text()
    elif head == "/clear":
        agent.history.messages.clear()
        agent.ctx.state.clear()
        ui.info("已清空历史。")
    elif head == "/compact":
        agent.history.compact(agent._summarize)
        ui.info("已压缩历史。")
    elif head == "/tokens":
        ui.info(f"上一回合 input_tokens ≈ {agent.history.last_input_tokens}")
    elif head == "/yolo":
        agent.permissions.yolo = not agent.permissions.yolo
        ui.info(f"yolo 模式: {'开' if agent.permissions.yolo else '关'}")
    elif head == "/memory":
        from . import memory

        for label, path in (
            ("全局记忆", memory.global_path()),
            ("项目记忆", memory.project_path(agent.config.workdir)),
        ):
            content = memory.read(path)
            ui.info(f"{label} ({path}):")
            ui.info(content if content else "（空）")
    # ---- 多会话命令 ----
    elif head == "/sessions":
        infos = agent.sessions.list() if agent.sessions else []
        ui.sessions_list(infos, agent.session_name)
    elif head == "/session":
        if not arg:
            ui.info(f"当前会话: {agent.session_name}")
        else:
            loaded = agent.switch_session(arg)
            if loaded:
                ui.info(f"已切换到会话「{arg}」（{len(agent.history.messages)} 条消息）。")
            else:
                ui.info(f"已新建并切换到会话「{arg}」。")
    elif head == "/new":
        name = agent.new_session(arg or None)
        ui.info(f"已开始新会话「{name}」。")
    elif head == "/delete":
        if not arg:
            ui.error("用法: /delete <会话名>")
        elif agent.sessions and agent.sessions.delete(arg):
            ui.info(f"已删除会话「{arg}」。")
            if arg == agent.session_name:
                name = agent.new_session()
                ui.info(f"（当前会话已被删除，切到新会话「{name}」）")
        else:
            ui.error(f"未找到会话「{arg}」。")
    else:
        ui.error(f"未知命令: {head}（/help 查看）")
    return False


def main() -> int:
    ui.ensure_utf8_io()  # 兜底：保证中文等多字节输入不会因终端编码崩溃
    args = parse_args()
    config = build_config(args)

    sessions = SessionManager(config.workdir)
    sessions.migrate_legacy(os.path.join(config.workdir, LEGACY_SESSION_FILE))

    try:
        agent = Agent(config, interactive=not args.prompt, sessions=sessions)
    except Exception as e:  # noqa: BLE001
        ui.error(f"初始化失败: {e}")
        ui.error("请检查 .env 里的 API key（参考 .env.example）。")
        return 1

    # 决定使用哪个会话
    resumed = False
    if args.session:
        name = args.session
        if sessions.exists(name):
            agent.session_name = name
            agent.history.load(sessions.path(name))
            resumed = True
        else:
            agent.session_name = name
    elif args.resume:
        # --resume 带名字则恢复该会话，否则恢复最近的
        name = args.resume if isinstance(args.resume, str) else sessions.latest()
        if name and sessions.exists(name):
            agent.session_name = name
            agent.history.load(sessions.path(name))
            resumed = True
        else:
            agent.session_name = sessions.default_name()
            ui.info("没有找到可恢复的会话，将开始新会话。")
    else:
        agent.session_name = sessions.default_name()

    if resumed:
        ui.info(
            f"已恢复会话「{agent.session_name}」（{len(agent.history.messages)} 条消息）。"
        )

    # 单次非交互模式
    if args.prompt:
        agent.interactive = True  # 仍然显示输出/确认
        agent.run_turn(args.prompt, images=extract_images(args.prompt))
        return 0

    # 交互式 REPL
    ui.banner(config.provider, config.resolved_model(), config.workdir)
    ui.info(f"当前会话: {agent.session_name}")
    while True:
        try:
            line = ui.user_prompt()
        except (EOFError, KeyboardInterrupt):
            ui.info("\n再见。")
            return 0

        line = line.strip()
        if not line:
            continue
        if is_command(line):
            if handle_command(line, agent):
                ui.info("再见。")
                return 0
            continue

        images = extract_images(line)
        if images:
            ui.info(f"（检测到 {len(images)} 张图片，将随消息一起发送）")
        try:
            agent.run_turn(line, images=images)
        except KeyboardInterrupt:
            ui.info("\n（已中断当前回合）")
        except Exception as e:  # noqa: BLE001
            ui.error(f"出错: {e}")


if __name__ == "__main__":
    sys.exit(main())
