"""Text-cleaning helpers used by deterministic transformations."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any, Iterable


_WHITESPACE = re.compile(r"\s+")
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "dl",
    "dt",
    "dd",
    "figcaption",
    "figure",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tr",
    "ul",
}


class _VisibleTextParser(HTMLParser):
    """Extract visible text while excluding script and style contents."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized_tag = tag.casefold()
        if normalized_tag in {"script", "style"}:
            self.hidden_depth += 1
        elif normalized_tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag in {"script", "style"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif normalized_tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0:
            self.parts.append(data)


def normalize_whitespace(value: str | None) -> str:
    """Collapse all whitespace and trim the result."""

    return _WHITESPACE.sub(" ", value or "").strip()


def html_to_text(value: str | None) -> str:
    """Convert possibly HTML-escaped Greenhouse content to plain text."""

    if not value:
        return ""

    decoded = value
    for _ in range(2):
        unescaped = html.unescape(decoded)
        if unescaped == decoded:
            break
        decoded = unescaped

    parser = _VisibleTextParser()
    parser.feed(decoded)
    parser.close()
    return normalize_whitespace(" ".join(parser.parts))


def clean_display_text(value: Any) -> str:
    """Return a safe, human-readable string from an external value."""

    if value is None:
        return ""
    return normalize_whitespace(html.unescape(str(value)))


def normalized_key(value: str | None) -> str:
    """Create a lower-case comparison key without changing display text."""

    text = clean_display_text(value).casefold()
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return normalize_whitespace(text)


def join_named_values(values: Any) -> str | None:
    """Join unique ``name`` fields from Greenhouse list objects."""

    if not isinstance(values, list):
        return None

    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        name = clean_display_text(value.get("name"))
        comparison_key = name.casefold()
        if name and comparison_key not in seen:
            names.append(name)
            seen.add(comparison_key)

    return ", ".join(names) or None


def unique_strings(values: Iterable[str]) -> tuple[str, ...]:
    """Preserve order while removing empty and duplicate strings."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean_value = normalize_whitespace(value)
        key = clean_value.casefold()
        if clean_value and key not in seen:
            result.append(clean_value)
            seen.add(key)
    return tuple(result)
