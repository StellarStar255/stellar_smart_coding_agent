"""工具注册表。"""

from __future__ import annotations

from .base import Tool, ToolContext, ToolOutput
from .bash import BashTool
from .edit_file import EditFileTool
from .glob_tool import GlobTool
from .grep import GrepTool
from .ls import LSTool
from .memory_tool import MemoryWriteTool
from .read_file import ReadFileTool
from .todo import TodoWriteTool
from .web import WebFetchTool, WebSearchTool
from .write_file import WriteFileTool


def default_tools(include_task: bool = True) -> list[Tool]:
    """返回默认工具集。子 agent 默认不再带 task（避免无限嵌套）。"""
    tools: list[Tool] = [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        BashTool(),
        GrepTool(),
        GlobTool(),
        LSTool(),
        TodoWriteTool(),
        MemoryWriteTool(),
        WebFetchTool(),
        WebSearchTool(),
    ]
    if include_task:
        from .task import TaskTool

        tools.append(TaskTool())
    return tools


__all__ = ["Tool", "ToolContext", "ToolOutput", "default_tools"]
