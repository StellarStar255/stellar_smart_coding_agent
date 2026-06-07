"""权限确认系统。

Claude Code 的安全核心：有副作用的工具（写文件、执行命令）在执行前
要征得用户同意。这里支持：每次询问 / 本会话记住某工具 / yolo 全放行。
"""

from __future__ import annotations

from enum import Enum


class Decision(Enum):
    ALLOW_ONCE = "allow_once"
    ALLOW_ALWAYS = "allow_always"  # 本会话内此工具不再询问
    DENY = "deny"


class PermissionManager:
    def __init__(self, yolo: bool = False):
        self.yolo = yolo
        self._always_allowed: set[str] = set()

    def is_pre_approved(self, tool_name: str) -> bool:
        return self.yolo or tool_name in self._always_allowed

    def remember(self, tool_name: str) -> None:
        self._always_allowed.add(tool_name)
