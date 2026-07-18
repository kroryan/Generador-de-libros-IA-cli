"""Bounded DuckDuckGo web search for the author agent."""

from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
from urllib.parse import parse_qs, unquote, urlparse

import requests


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._field = ""
        self._href = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._field = "title"
            self._href = attributes.get("href") or ""
            self._buffer = []
        elif tag in {"a", "div"} and "result__snippet" in classes:
            self._field = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._field:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._field == "title" and tag == "a":
            title = _clean(" ".join(self._buffer))
            if title and self._href:
                self.results.append({"title": title, "url": _result_url(self._href), "snippet": ""})
            self._field = ""
            self._buffer = []
        elif self._field == "snippet" and tag in {"a", "div"}:
            snippet = _clean(" ".join(self._buffer))
            if snippet and self.results and not self.results[-1]["snippet"]:
                self.results[-1]["snippet"] = snippet
            self._field = ""
            self._buffer = []


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in {"p", "li", "h1", "h2", "h3", "h4", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            value = _clean(data)
            if value:
                self.parts.append(value + " ")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _result_url(value: str) -> str:
    parsed = urlparse(value)
    redirected = parse_qs(parsed.query).get("uddg", [])
    return unquote(redirected[0]) if redirected else value


def _validate_public_url(value: str) -> str:
    parsed = urlparse(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) source URLs are allowed")
    if parsed.hostname.casefold() in {"localhost", "localhost.localdomain"}:
        raise ValueError("Local web addresses are blocked")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as error:
        raise ValueError(f"Source hostname could not be resolved: {error}") from error
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private, loopback, link-local, and reserved web addresses are blocked")
    return parsed.geturl()


def search_duckduckgo(query: str, limit: int = 5) -> list[dict[str, str]]:
    query = _clean(str(query))[:300]
    if not query:
        raise ValueError("A web search query is required")
    response = requests.get(
        os.getenv("DUCKDUCKGO_SEARCH_URL", "https://html.duckduckgo.com/html/"),
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 BookGenResearch/1.0"},
        timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "12")),
    )
    response.raise_for_status()
    parser = _DuckDuckGoParser()
    parser.feed(response.text)
    selected = []
    for item in parser.results:
        parsed = urlparse(item["url"])
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            selected.append(item)
        if len(selected) >= max(1, min(int(limit), 8)):
            break
    return selected


def read_public_page(url: str, max_chars: int = 8000) -> dict[str, str]:
    requested_url = _validate_public_url(url)
    response = requests.get(
        requested_url,
        headers={"User-Agent": "Mozilla/5.0 BookGenResearch/1.0"},
        timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "12")),
        allow_redirects=True,
    )
    response.raise_for_status()
    final_url = _validate_public_url(response.url)
    content_type = response.headers.get("content-type", "").casefold()
    if not any(value in content_type for value in ("text/html", "text/plain", "application/xhtml+xml")):
        raise ValueError(f"Unsupported source content type: {content_type or 'unknown'}")
    raw = response.content[:int(os.getenv("WEB_PAGE_MAX_BYTES", "1500000"))]
    decoded = raw.decode(response.encoding or "utf-8", errors="replace")
    if "html" in content_type or "xhtml" in content_type:
        parser = _ReadableTextParser()
        parser.feed(decoded)
        text = "".join(parser.parts)
    else:
        text = decoded
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return {"url": final_url, "content": text[:max(1000, min(int(max_chars), 16000))]}
