"""Anthropic (Claude) provider。

负责：内部 Message 列表  <->  Anthropic messages 格式 的互转，
以及流式解析 tool_use。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..messages import (
    AssistantMessage,
    Done,
    Message,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallStart,
    ToolSpec,
    Usage,
)
from .base import Provider


class AnthropicProvider(Provider):
    def __init__(self, api_key: str | None, model: str, max_tokens: int = 8096):
        import anthropic

        if not api_key:
            raise RuntimeError("缺少 ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    # ---- 内部格式 -> Anthropic 格式 ----

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "user":
                out.append({"role": "user", "content": m.text})
            elif m.role == "assistant":
                content: list[dict[str, Any]] = []
                if m.text:
                    content.append({"type": "text", "text": m.text})
                for tc in m.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                out.append({"role": "assistant", "content": content})
            elif m.role == "tool":
                # Anthropic 把工具结果放在一条 user 消息里
                content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": r.tool_call_id,
                        "content": r.content,
                        "is_error": r.is_error,
                    }
                    for r in m.tool_results
                ]
                out.append({"role": "user", "content": content})
        return out

    def _convert_tools(self, tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    # ---- 流式 ----

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
    ) -> Iterator[StreamEvent]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=self._convert_messages(messages),
            tools=self._convert_tools(tools),
        ) as stream:
            for event in stream:
                if (
                    event.type == "content_block_delta"
                    and event.delta.type == "text_delta"
                ):
                    yield TextDelta(event.delta.text)
                elif (
                    event.type == "content_block_start"
                    and event.content_block.type == "tool_use"
                ):
                    yield ToolCallStart(event.content_block.name)
            final = stream.get_final_message()

        text = ""
        tool_calls: list[ToolCall] = []
        for block in final.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(block.id, block.name, dict(block.input)))

        usage = Usage(final.usage.input_tokens, final.usage.output_tokens)
        yield Done(AssistantMessage(text, tool_calls, usage))
