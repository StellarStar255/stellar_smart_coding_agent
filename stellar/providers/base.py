"""Provider 抽象：把统一的内部消息格式翻译给具体模型 API。

这是支持「多模型」的关键。agent 核心只依赖这个接口，
不关心底层是 Claude 的 tool_use 还是 OpenAI 的 function calling。
"""

from __future__ import annotations

import base64
import mimetypes
from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..messages import Message, StreamEvent, ToolSpec


def encode_image(path: str) -> tuple[str, str] | None:
    """把图片文件读成 (mime_type, base64)。

    两家 API 的图片格式不同，但都需要 mime + base64，所以编码放在这里共用。
    文件不存在/读不了/不是图片时返回 None，由调用方降级处理——
    历史里只存路径，恢复旧会话时图片文件可能已被清理。
    """
    mime, _ = mimetypes.guess_type(path)
    if not mime or not mime.startswith("image/"):
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    return mime, base64.b64encode(data).decode("ascii")


class Provider(ABC):
    """所有模型 provider 的统一接口。"""

    model: str

    @abstractmethod
    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        """流式生成一个 assistant 回合。

        产出一串 TextDelta（用于实时显示），最后产出一个 Done
        （携带完整的 AssistantMessage，包含 text + tool_calls + usage）。
        """
        raise NotImplementedError
