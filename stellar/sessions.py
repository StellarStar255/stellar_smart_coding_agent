"""多会话管理。

每个会话是 `.stellar/sessions/<name>.json` 一个文件。
支持命名、列表、切换、删除，以及把旧版单文件会话迁移过来。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime


def sanitize_name(name: str) -> str:
    """清洗会话名，防止路径穿越和非法文件名。"""
    name = name.strip().replace(" ", "-")
    name = re.sub(r"[^\w\-.]", "_", name)  # 只保留字母数字下划线连字符点
    return name or "session"


@dataclass
class SessionInfo:
    name: str
    path: str
    modified: float
    num_messages: int
    preview: str


class SessionManager:
    def __init__(self, workdir: str):
        self.dir = os.path.join(workdir, ".stellar", "sessions")

    def _ensure(self) -> None:
        os.makedirs(self.dir, exist_ok=True)

    def path(self, name: str) -> str:
        return os.path.join(self.dir, f"{sanitize_name(name)}.json")

    def exists(self, name: str) -> bool:
        return os.path.isfile(self.path(name))

    def default_name(self) -> str:
        """新会话的自动名字：时间戳。"""
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    def list(self) -> list[SessionInfo]:
        """列出所有会话，按最近修改时间倒序。"""
        if not os.path.isdir(self.dir):
            return []
        infos: list[SessionInfo] = []
        for fn in sorted(os.listdir(self.dir)):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(self.dir, fn)
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                msgs = data.get("messages", [])
                preview = next(
                    (m.get("text", "") for m in msgs if m.get("role") == "user"),
                    "",
                )
            except (OSError, json.JSONDecodeError):
                msgs, preview = [], ""
            infos.append(
                SessionInfo(
                    name=fn[:-5],
                    path=p,
                    modified=os.path.getmtime(p),
                    num_messages=len(msgs),
                    preview=preview[:60],
                )
            )
        infos.sort(key=lambda i: i.modified, reverse=True)
        return infos

    def latest(self) -> str | None:
        infos = self.list()
        return infos[0].name if infos else None

    def delete(self, name: str) -> bool:
        p = self.path(name)
        if os.path.isfile(p):
            os.remove(p)
            return True
        return False

    def migrate_legacy(self, legacy_path: str) -> None:
        """把旧版 .stellar/session.json 迁移成 sessions/default.json。"""
        if os.path.isfile(legacy_path) and not self.list():
            self._ensure()
            try:
                shutil.move(legacy_path, self.path("default"))
            except OSError:
                pass
