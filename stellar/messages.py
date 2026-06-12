"""统一的内部消息表示。

关键设计：我们定义一套与具体模型 API 无关的消息结构，
然后每个 provider 负责把它「翻译」成 Anthropic / OpenAI 各自的格式。
这样 agent 的核心逻辑就完全不用关心底层用的是哪家模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """模型请求调用某个工具。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """一次工具调用的执行结果，要喂回给模型。"""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """对话历史中的一条消息。

    role:
      - "user"      : 用户输入（text + 可选的 images）
      - "assistant" : 模型回复（text + 可选的 tool_calls）
      - "tool"      : 工具执行结果（tool_results，可能一次多个）
    """

    role: str
    text: str = ""
    # 随消息附带的图片，存文件路径而非 base64：历史存档因此保持轻量，
    # 由 provider 在发送时才读文件编码；文件已被删除时由 provider 容错。
    images: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "images": list(self.images),
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ],
            "tool_results": [
                {
                    "tool_call_id": r.tool_call_id,
                    "content": r.content,
                    "is_error": r.is_error,
                }
                for r in self.tool_results
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Message":
        return cls(
            role=d["role"],
            text=d.get("text", ""),
            images=d.get("images", []),
            tool_calls=[
                ToolCall(tc["id"], tc["name"], tc["arguments"])
                for tc in d.get("tool_calls", [])
            ],
            tool_results=[
                ToolResult(r["tool_call_id"], r["content"], r.get("is_error", False))
                for r in d.get("tool_results", [])
            ],
        )


@dataclass
class Usage:
    """token 用量统计。"""

    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


@dataclass
class AssistantMessage:
    """模型一个回合的完整输出。"""

    text: str
    tool_calls: list[ToolCall]
    usage: Usage


# ---- 流式事件：provider.stream() 产出的事件类型 ----


@dataclass
class TextDelta:
    """流式文本增量。"""

    text: str


@dataclass
class ToolCallStart:
    """流式中模型刚开始调用某工具（名字已知，参数还在生成）。"""

    name: str


@dataclass
class Done:
    """一个回合结束，携带完整的 AssistantMessage。"""

    message: AssistantMessage


StreamEvent = TextDelta | ToolCallStart | Done


@dataclass
class ToolSpec:
    """提供给模型的工具描述（JSON Schema）。"""

    name: str
    description: str
    parameters: dict[str, Any]
