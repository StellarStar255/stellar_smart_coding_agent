"""联网工具：WebFetch（抓网页转文本）和 WebSearch（搜索）。

只用标准库 urllib，不引入额外依赖。
- WebFetch: 抓取 URL，HTML 用内置解析器粗略转成纯文本。
- WebSearch: 走 DuckDuckGo 的 lite HTML 端点（无需 API key）解析结果。
注意：网页抓取/搜索结果格式会变，这里是教学级实现，够用但不保证稳健。
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from .base import Tool, ToolContext, ToolOutput

UA = "Mozilla/5.0 (compatible; StellarAgent/0.1)"
MAX_TEXT = 20_000


def _fetch(url: str, timeout: int = 20) -> tuple[str, str]:
    """返回 (content_type, body_text)。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        ctype = resp.headers.get("Content-Type", "")
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read()
    return ctype, raw.decode(charset, errors="replace")


class _TextExtractor(HTMLParser):
    """把 HTML 粗略抽成纯文本：丢弃 script/style，保留可见文字。"""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            text = data.strip()
            if text:
                self.parts.append(text + " ")


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", html)  # 退化：直接去标签
    text = "".join(p.parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "抓取一个 URL 的内容。HTML 会转成纯文本返回，适合读文档/文章/报错页面。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的完整 URL"},
        },
        "required": ["url"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        url = args["url"]
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            ctype, body = _fetch(url)
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"抓取失败: {e}", is_error=True)
        text = html_to_text(body) if "html" in ctype.lower() else body
        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT] + "\n…(内容过长已截断)"
        return ToolOutput(text or "(空内容)")


class _DDGParser(HTMLParser):
    """解析 DuckDuckGo lite 结果页：抓 result link 的标题与 url。"""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, str]] = []
        self._in_result_link = False
        self._href = ""
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "a":
            d = dict(attrs)
            cls = d.get("class", "") or ""
            if "result-link" in cls:
                self._in_result_link = True
                self._href = d.get("href", "")
                self._title_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            title = "".join(self._title_parts).strip()
            if title and self._href:
                self.results.append((title, self._href))
            self._in_result_link = False

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._title_parts.append(data)


class WebSearchTool(Tool):
    name = "web_search"
    description = "用 DuckDuckGo 联网搜索，返回前若干条结果的标题和链接。用于查资料/找文档。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "max_results": {"type": "integer", "description": "返回条数，默认 8"},
        },
        "required": ["query"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> ToolOutput:
        query = args["query"]
        n = args.get("max_results", 8)
        url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode(
            {"q": query}
        )
        try:
            _, body = _fetch(url)
        except Exception as e:  # noqa: BLE001
            return ToolOutput(f"搜索失败: {e}", is_error=True)
        parser = _DDGParser()
        parser.feed(body)
        if not parser.results:
            return ToolOutput("(无结果，或页面结构已变化)")
        lines = []
        for i, (title, href) in enumerate(parser.results[:n], 1):
            # ddg lite 的链接可能是跳转包装，尝试还原真实 url
            real = href
            m = re.search(r"uddg=([^&]+)", href)
            if m:
                real = urllib.parse.unquote(m.group(1))
            lines.append(f"{i}. {title}\n   {real}")
        return ToolOutput("\n".join(lines))
