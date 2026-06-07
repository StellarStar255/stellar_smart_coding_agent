"""精确字符串替换编辑（类似 Claude Code 的 Edit）。有副作用，需要确认。"""

from __future__ import annotations

import os
from typing import Any

from .base import Tool, ToolContext, ToolOutput, make_diff


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "在文件中把 old_string 替换为 new_string。old_string 必须在文件中"
        "唯一出现（否则报错），除非 replace_all=true。用于精确修改而非整体覆盖。"
    )
    requires_permission = True
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_string": {"type": "string", "description": "要被替换的原文（需精确匹配，含缩进）"},
            "new_string": {"type": "string", "description": "替换后的新文本"},
            "replace_all": {
                "type": "boolean",
                "description": "是否替换所有出现，默认 false",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }

    def preview(self, args: dict[str, Any]) -> str:
        return f"编辑文件 {args.get('path')}（替换一段文本）"

    def diff_preview(self, args: dict[str, Any], ctx: ToolContext) -> str | None:
        path = os.path.join(ctx.workdir, args.get("path", ""))
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                old = f.read()
        except OSError:
            return None
        olds = args.get("old_string", "")
        news = args.get("new_string", "")
        if olds not in old:
            return None
        if args.get("replace_all"):
            new = old.replace(olds, news)
        else:
            new = old.replace(olds, news, 1)
        return make_diff(old, new, args.get("path", "")) or None

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        path = os.path.join(ctx.workdir, args["path"])
        if not os.path.exists(path):
            return ToolOutput(f"文件不存在: {path}", is_error=True)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"读取失败: {e}", is_error=True)

        old = args["old_string"]
        new = args["new_string"]
        replace_all = args.get("replace_all", False)

        count = content.count(old)
        if count == 0:
            return ToolOutput("未找到 old_string，无法替换。", is_error=True)
        if count > 1 and not replace_all:
            return ToolOutput(
                f"old_string 出现了 {count} 次，不唯一。请提供更多上下文，"
                "或设置 replace_all=true。",
                is_error=True,
            )

        updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"写入失败: {e}", is_error=True)

        n = count if replace_all else 1
        return ToolOutput(f"已在 {path} 替换 {n} 处。")
