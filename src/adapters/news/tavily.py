"""Tavily-backed search adapter for current data-center industry news."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

import httpx

from src.domain.errors import NewsSourceError
from src.domain.models import NewsItem

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_DOMAINS = (
    "newsroom.equinix.com",
    "datacenterdynamics.com",
    "datacenterfrontier.com",
)
SEARCH_QUERY = (
    "specific recent data center industry news article about a concrete event: "
    "new facility, expansion, acquisition, investment, power, cooling, outage, "
    "regulation, sustainability, chips or AI infrastructure; exclude homepages, "
    "category pages, podcasts, broadcasts and descriptions of publications"
)
MAX_SOURCE_CHARS = 8_000

_NON_ARTICLE_SLUGS = frozenset(
    {
        "blog",
        "news",
        "newsroom",
        "press-releases-global",
        "dcd-broadcasts",
        "podcasts",
        "events",
    }
)
_ALLOWED_HOSTS = frozenset(DEFAULT_DOMAINS)
_PUBLISHED_AT_PATTERNS = (
    re.compile(r'"datePublished"\s*:\s*"([^"<]+)"', re.IGNORECASE),
    re.compile(
        r'article:published_time[^>]+content=["\']([^"\']+)', re.IGNORECASE
    ),
    re.compile(r'<time[^>]+datetime=["\']([^"\']+)', re.IGNORECASE),
)


class TavilyNewsSource:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str,
        domains: Sequence[str] = DEFAULT_DOMAINS,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._domains = tuple(domains)

    async def search(self, limit: int) -> tuple[NewsItem, ...]:
        try:
            response = await self._client.post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "query": SEARCH_QUERY,
                    "topic": "news",
                    "search_depth": "basic",
                    "time_range": "month",
                    # Ask for extra candidates because category/home pages are
                    # rejected locally before the port result is returned.
                    "max_results": min(max(limit * 2, 10), 20),
                    "include_domains": list(self._domains),
                    "include_answer": False,
                    "include_raw_content": "text",
                    "include_images": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise NewsSourceError("News search request failed") from exc

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise NewsSourceError("News search returned an invalid response")

        items: list[NewsItem] = []
        for raw in results:
            item = self._parse_item(raw)
            if item is not None:
                if item.published_at is None:
                    published_at = await self._fetch_published_at(item.url)
                    if published_at:
                        item = replace(item, published_at=published_at)
                items.append(item)
            if len(items) == limit:
                break
        return tuple(items)

    @staticmethod
    def _parse_item(raw: Any) -> NewsItem | None:
        if not isinstance(raw, dict):
            return None
        title = raw.get("title")
        url = raw.get("url")
        raw_content = raw.get("raw_content")
        summary = raw_content if isinstance(raw_content, str) and raw_content.strip() else raw.get("content")
        if not all(isinstance(value, str) and value.strip() for value in (title, url, summary)):
            return None
        if not TavilyNewsSource._is_article_url(url):
            return None
        published_at = raw.get("published_date")
        if not isinstance(published_at, str):
            published_at = None
        try:
            return NewsItem(
                title=title.strip(),
                url=url.strip(),
                summary=summary.strip()[:MAX_SOURCE_CHARS],
                published_at=published_at,
            )
        except ValueError:
            return None

    async def _fetch_published_at(self, url: str) -> str | None:
        """Best-effort metadata lookup when Tavily omits the article date."""
        try:
            response = await self._client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": "AkashiMedia/0.1 (+data-center-digest)"},
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        for pattern in _PUBLISHED_AT_PATTERNS:
            match = pattern.search(response.text)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _is_article_url(url: str) -> bool:
        parsed = urlparse(url)
        segments = [segment.casefold() for segment in parsed.path.split("/") if segment]
        if len(segments) < 2 or segments[-1] in _NON_ARTICLE_SLUGS:
            return False

        host = (parsed.hostname or "").casefold()
        if not any(host == allowed or host.endswith(f".{allowed}") for allowed in _ALLOWED_HOSTS):
            return False
        if host.endswith("datacenterdynamics.com"):
            # Real DCD stories follow /en/news/<story>/, /en/analysis/<story>/,
            # etc.; /en/news/ and /en/dcd-broadcasts/ are listing pages.
            return len(segments) >= 3 and segments[1] in {"news", "analysis"}
        if host == "blog.equinix.com":
            # Equinix articles follow /blog/YYYY/MM/DD/<slug>/.
            return len(segments) >= 5 and segments[0] == "blog"
        if host == "newsroom.equinix.com":
            return len(segments) >= 3
        return bool(segments)
