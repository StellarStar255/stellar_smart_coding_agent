"""配置加载：环境变量 + 命令行覆盖。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    # 先加载当前目录的 .env（每个项目可有自己的覆盖配置），
    # 再加载本程序安装目录的 .env 作为兜底——这样在任意文件夹下
    # 输入 stellar 启动时，都能找到 API key。
    # load_dotenv 默认不覆盖已存在的变量，所以「先加载的优先」。
    load_dotenv()
    _pkg_root = Path(__file__).resolve().parent.parent
    load_dotenv(_pkg_root / ".env")
except ImportError:  # dotenv 可选
    pass


DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
}


@dataclass
class Config:
    provider: str = "anthropic"
    model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # 最大输出 token
    max_tokens: int = 8096
    # 当上一回合的 input_tokens 超过这个阈值时，触发历史压缩
    compact_threshold: int = 120_000
    # 工作目录
    workdir: str = "."
    # yolo 模式：跳过所有权限确认（危险，自用学习时方便）
    yolo: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        provider = os.environ.get("STELLAR_PROVIDER", "anthropic").lower()
        model = os.environ.get("STELLAR_MODEL") or None
        return cls(
            provider=provider,
            model=model or DEFAULT_MODELS.get(provider),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_base_url=os.environ.get("OPENAI_BASE_URL"),
        )

    def resolved_model(self) -> str:
        return self.model or DEFAULT_MODELS.get(self.provider, "")
