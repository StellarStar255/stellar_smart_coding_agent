"""持久记忆：跨会话记住用户是谁、coding 习惯和项目约定。

设计模仿 Claude Code 的 CLAUDE.md 机制——记忆就是普通 Markdown 文件，
人和 agent 都能读写：

- 全局记忆  ~/.stellar/memory.md        用户身份、编码习惯、通用要求（跨项目）
- 项目记忆  <workdir>/.stellar/memory.md  当前项目的约定、背景、长期任务

每次构建 system prompt 时把两份文件原样注入；agent 通过 memory_write
工具追加/重写条目。文件不存在 = 没有记忆，一切从零开始。
"""

from __future__ import annotations

import os

# 防止把超长内容塞进 system prompt 挤爆上下文
MAX_MEMORY_CHARS = 8_000

GLOBAL_DIR = os.path.expanduser("~/.stellar")


def global_path() -> str:
    return os.path.join(GLOBAL_DIR, "memory.md")


def project_path(workdir: str) -> str:
    return os.path.join(os.path.abspath(workdir), ".stellar", "memory.md")


def resolve_path(scope: str, workdir: str) -> str:
    return global_path() if scope == "global" else project_path(workdir)


def read(path: str) -> str:
    """读取记忆文件内容；不存在或读取失败返回空串。"""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return ""
    if len(text) > MAX_MEMORY_CHARS:
        text = text[:MAX_MEMORY_CHARS] + "\n…(记忆过长已截断，建议用 replace 模式精简)"
    return text


def append(path: str, content: str) -> None:
    """向记忆文件追加一条记忆（自动建目录、补换行和列表符号）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = content.strip()
    if not content.startswith(("-", "*", "#")):
        content = f"- {content}"
    old = read(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write((old + "\n" if old else "") + content + "\n")


def replace(path: str, content: str) -> None:
    """用新内容整体重写记忆文件（用于整理、修正或删除过期记忆）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")


def render_for_prompt(workdir: str) -> str:
    """渲染成 system prompt 里的「记忆」段落；没有任何记忆时返回空串。"""
    sections = []
    g = read(global_path())
    if g:
        sections.append(f"## 全局记忆（用户身份与习惯）\n{g}")
    p = read(project_path(workdir))
    if p:
        sections.append(f"## 项目记忆（本项目约定）\n{p}")
    return "\n\n".join(sections)
