from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any, Iterable


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif self._skip_depth == 0 and lowered in {
            "p", "div", "br", "li", "ul", "ol", "section", "h1", "h2", "h3", "h4"
        }:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            if self._skip_depth:
                self._skip_depth -= 1
        elif self._skip_depth == 0 and lowered in {"p", "div", "li", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def compact_text(value: Any) -> str:
    text = html.unescape(str(value or "")).replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def html_to_text(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parser = _VisibleTextParser()
    try:
        parser.feed(raw)
        parser.close()
        return compact_text("".join(parser.parts))
    except Exception:
        return compact_text(re.sub(r"<[^>]+>", " ", raw))


def join_sections(sections: Iterable[tuple[str, Any]]) -> str:
    output: list[str] = []
    for heading, value in sections:
        cleaned = html_to_text(value)
        if not cleaned:
            continue
        if heading:
            output.append(f"{heading}\n{cleaned}")
        else:
            output.append(cleaned)
    return "\n\n".join(output).strip()


def query_tokens(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9+#.]+", str(query or "").lower())
        if len(token) >= 2
    ]


def matches_query(query: str, *values: Any) -> bool:
    tokens = query_tokens(query)
    if not tokens:
        return True
    haystack = " ".join(str(value or "") for value in values).lower()
    return all(token in haystack for token in tokens)


def looks_singapore_location(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(
        marker in text
        for marker in (
            "singapore",
            "sgp",
            "sg -",
            ", sg",
            "sg 0",
        )
    )


def list_text(value: Any) -> str:
    if isinstance(value, str):
        return compact_text(value)
    if isinstance(value, dict):
        for key in ("name", "label", "value", "text"):
            candidate = value.get(key)
            if candidate:
                return compact_text(candidate)
        return ""
    if isinstance(value, list):
        parts = [list_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    return compact_text(value)
