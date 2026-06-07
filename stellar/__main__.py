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
import sys

from .agent import Agent
from .config import Config
from . import ui


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="stellar", description="Stellar 编码 agent")
    p.add_argument("--provider", choices=["anthropic", "openai"], help="模型 provider")
    p.add_argument("--model", help="模型名")
    p.add_argument("--workdir", default=".", help="工作目录")
    p.add_argument("--yolo", action="store_true", help="跳过所有权限确认")
    p.add_argument("-p", "--prompt", help="单次执行该提示后退出（非交互）")
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
    if cmd in ("/exit", "/quit"):
        return True
    if cmd == "/help":
        ui.help_text()
    elif cmd == "/clear":
        agent.history.messages.clear()
        agent.ctx.state.clear()
        ui.info("已清空历史。")
    elif cmd == "/compact":
        agent.history.compact(agent._summarize)
        ui.info("已压缩历史。")
    elif cmd == "/tokens":
        ui.info(f"上一回合 input_tokens ≈ {agent.history.last_input_tokens}")
    elif cmd == "/yolo":
        agent.permissions.yolo = not agent.permissions.yolo
        ui.info(f"yolo 模式: {'开' if agent.permissions.yolo else '关'}")
    else:
        ui.error(f"未知命令: {cmd}（/help 查看）")
    return False


def main() -> int:
    args = parse_args()
    config = build_config(args)

    try:
        agent = Agent(config, interactive=not args.prompt)
    except Exception as e:  # noqa: BLE001
        ui.error(f"初始化失败: {e}")
        ui.error("请检查 .env 里的 API key（参考 .env.example）。")
        return 1

    # 单次非交互模式
    if args.prompt:
        agent.interactive = True  # 仍然显示输出/确认
        agent.run_turn(args.prompt)
        return 0

    # 交互式 REPL
    ui.banner(config.provider, config.resolved_model(), config.workdir)
    while True:
        try:
            line = ui.user_prompt()
        except (EOFError, KeyboardInterrupt):
            ui.info("\n再见。")
            return 0

        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            if handle_command(line, agent):
                ui.info("再见。")
                return 0
            continue

        try:
            agent.run_turn(line)
        except KeyboardInterrupt:
            ui.info("\n（已中断当前回合）")
        except Exception as e:  # noqa: BLE001
            ui.error(f"出错: {e}")


if __name__ == "__main__":
    sys.exit(main())
