"""工具基类与上下文。

每个工具声明自己的 JSON Schema（给模型看），并实现 run()。
模型通过 tool_call 触发 run()，结果以字符串返回，再喂回模型。
"""

from __future__ import annotations

import difflib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..messages import ToolSpec


def make_diff(old: str, new: str, path: str) -> str:
    """生成 unified diff 文本。无变化则返回空串。"""
    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    return "\n".join(diff)


@dataclass
class ToolContext:
    """工具执行时可访问的运行环境。"""

    workdir: str
    # 共享状态，例如 TodoWrite 写、其它工具读
    state: dict[str, Any] = field(default_factory=dict)
    # 用于 task 子 agent：回指主程序的一些能力
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    content: str
    is_error: bool = False


class Tool(ABC):
    name: str
    description: str
    # JSON Schema（properties / required ...）
    parameters: dict[str, Any]
    # 是否需要用户确认（写文件、执行命令等有副作用的操作 = True）
    requires_permission: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)

    def preview(self, args: dict[str, Any]) -> str:
        """权限确认时，向用户展示「将要做什么」的简短描述。"""
        return f"{self.name}({args})"

    def diff_preview(self, args: dict[str, Any], ctx: "ToolContext") -> str | None:
        """确认前展示给用户的 unified diff（无则返回 None）。

        写文件/编辑文件类工具可重写它，让用户在批准前看清改动。
        """
        return None

    @abstractmethod
    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        raise NotImplementedError
