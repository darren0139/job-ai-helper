from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlsplit

from job_discovery.text_utils import compact_text, html_to_text


class _LinkAndHeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.headings: list[tuple[str, str]] = []
        self.title = ""
        self._active_link: str | None = None
        self._link_parts: list[str] = []
        self._active_heading: str | None = None
        self._heading_parts: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        lowered = tag.lower()
        attr_map = {str(key).lower(): value for key, value in attrs}
        if lowered == "a":
            href = str(attr_map.get("href") or "").strip()
            if href:
                self._active_link = href
                self._link_parts = []
        elif lowered in {"h1", "h2", "h3"}:
            self._active_heading = lowered
            self._heading_parts = []
        elif lowered == "title":
            self._in_title = True
            self._title_parts = []

    def handle_data(self, data: str) -> None:
        if self._active_link is not None:
            self._link_parts.append(data)
        if self._active_heading is not None:
            self._heading_parts.append(data)
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "a" and self._active_link is not None:
            self.links.append(
                (
                    self._active_link,
                    compact_text(" ".join(self._link_parts)),
                )
            )
            self._active_link = None
            self._link_parts = []
        elif (
            lowered in {"h1", "h2", "h3"}
            and self._active_heading == lowered
        ):
            value = compact_text(" ".join(self._heading_parts))
            if value:
                self.headings.append((lowered, value))
            self._active_heading = None
            self._heading_parts = []
        elif lowered == "title" and self._in_title:
            self.title = compact_text(" ".join(self._title_parts))
            self._in_title = False
            self._title_parts = []


def parse_document(html: str) -> _LinkAndHeadingParser:
    parser = _LinkAndHeadingParser()
    parser.feed(str(html or ""))
    parser.close()
    return parser


def visible_lines(html: str) -> list[str]:
    return [
        line.strip()
        for line in html_to_text(html).splitlines()
        if line.strip()
    ]


def extract_links(
    html: str,
    *,
    base_url: str,
    path_pattern: str,
) -> list[tuple[str, str]]:
    regex = re.compile(path_pattern, re.IGNORECASE)
    output: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, label in parse_document(html).links:
        absolute = urljoin(base_url, href)
        path = urlsplit(absolute).path
        if not regex.search(path):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        output.append((absolute, label))
    return output


def first_h1(html: str) -> str:
    for tag, value in parse_document(html).headings:
        if tag == "h1":
            return value
    return ""


def document_title(html: str) -> str:
    return parse_document(html).title


def section_lines(
    lines: Iterable[str],
    *,
    start_markers: tuple[str, ...],
    stop_markers: tuple[str, ...],
) -> list[str]:
    values = list(lines)
    start_index: int | None = None
    for index, value in enumerate(values):
        if any(
            value.casefold() == marker.casefold()
            for marker in start_markers
        ):
            start_index = index + 1
            break
    if start_index is None:
        return []

    result: list[str] = []
    for value in values[start_index:]:
        if any(
            value.casefold() == marker.casefold()
            for marker in stop_markers
        ):
            break
        result.append(value)
    return result


def deterministic_id(*parts: str, size: int = 20) -> str:
    material = "\n".join(
        str(part or "").strip().casefold()
        for part in parts
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:size]
