"""对话历史 + 自动压缩(compaction)。

上下文窗口有限。当历史太长（上一回合的 input_tokens 超过阈值）时，
我们让模型把较早的对话总结成一段话，用总结替换掉旧消息，从而腾出空间。
这就是 Claude Code "/compact" 背后的原理。
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from .messages import Message


class History:
    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.last_input_tokens: int = 0

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def add_user(self, text: str, images: list[str] | None = None) -> None:
        self.add(Message(role="user", text=text, images=images or []))

    def __len__(self) -> int:
        return len(self.messages)

    def needs_compaction(self, threshold: int) -> bool:
        return self.last_input_tokens > threshold

    # ---- 持久化（用于 --resume）----

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        data = {
            "last_input_tokens": self.last_input_tokens,
            "messages": [m.to_dict() for m in self.messages],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> bool:
        """从文件恢复历史，成功返回 True。"""
        if not os.path.isfile(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        self.messages = [Message.from_dict(d) for d in data.get("messages", [])]
        self.last_input_tokens = data.get("last_input_tokens", 0)
        return True

    def compact(
        self,
        summarize: Callable[[list[Message]], str],
        keep_recent: int = 4,
    ) -> None:
        """把除最近 keep_recent 条之外的历史压缩成一条 summary。

        summarize: 调用模型生成总结的函数（注入，避免 history 依赖 provider）。
        """
        if len(self.messages) <= keep_recent + 2:
            return
        # 保证不在工具调用/结果中间切断：让 recent 从一条 user 消息开始
        split = len(self.messages) - keep_recent
        while split > 0 and self.messages[split].role == "tool":
            split += 1  # 工具结果必须跟着它的 assistant tool_call，往后挪
        older = self.messages[:split]
        recent = self.messages[split:]
        if not older:
            return

        summary_text = summarize(older)
        summary_msg = Message(
            role="user",
            text="[此前对话的压缩摘要]\n" + summary_text,
        )
        self.messages = [summary_msg] + recent
        self.last_input_tokens = 0  # 重置，下个回合重新计量
