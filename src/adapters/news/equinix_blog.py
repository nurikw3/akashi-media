"""Latest relevant Equinix Blog article, exposed through its WordPress API."""

from __future__ import annotations

import html
import json
import re
from typing import Any

import httpx

from src.domain.errors import NewsSourceError
from src.domain.models import NewsItem

# The Equinix site blocks server-to-server reads. Jina Reader retrieves the
# public WordPress response unchanged enough for its JSON payload to be parsed.
_READER_PREFIX = "https://r.jina.ai/http://"
_WORDPRESS_POSTS_URL = (
    "https://blog.equinix.com/wp-json/wp/v2/posts?per_page=1"
    "&search=data%20center&orderby=date&order=desc"
    "&_fields=date,date_gmt,link,title,excerpt,acf.tldr_content,acf.teaser_text"
)
_RELEVANT_TERMS = (
    "data center",
    "datacenter",
    "data-centre",
    "infrastructure",
    "interconnection",
    "cooling",
    "heat export",
    "power",
    "energy",
    "ai",
    "cloud",
)
_TAG_RE = re.compile(r"<[^>]+>")


class EquinixBlogSource:
    """Provides the newest Equinix expert article relevant to data centers."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, limit: int) -> tuple[NewsItem, ...]:
        try:
            response = await self._client.get(
                f"{_READER_PREFIX}{_WORDPRESS_POSTS_URL}",
                headers={"Accept": "text/plain"},
            )
            response.raise_for_status()
            posts = self._decode_posts(response.text)
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise NewsSourceError("Equinix Blog request failed") from exc

        items: list[NewsItem] = []
        for post in posts:
            item = self._to_item(post)
            if item is None:
                continue
            items.append(item)
            if len(items) == limit:
                break
        return tuple(items)

    @staticmethod
    def _decode_posts(body: str) -> list[dict[str, Any]]:
        marker = "Markdown Content:"
        start = body.find(marker)
        if start == -1:
            raise ValueError("Reader response does not contain WordPress content")
        json_start = body.find("[", start + len(marker))
        if json_start == -1:
            raise ValueError("WordPress posts array is missing")
        # Jina can preserve line breaks from WordPress HTML fields without
        # escaping them. They are harmless to us after markup cleanup.
        decoded, _ = json.JSONDecoder(strict=False).raw_decode(body[json_start:])
        if not isinstance(decoded, list):
            raise ValueError("WordPress posts response is invalid")
        return [post for post in decoded if isinstance(post, dict)]

    @classmethod
    def _to_item(cls, post: dict[str, Any]) -> NewsItem | None:
        title_data = post.get("title")
        title = title_data.get("rendered") if isinstance(title_data, dict) else None
        url = post.get("link")
        acf = post.get("acf")
        if not isinstance(acf, dict):
            acf = {}
        summary = acf.get("tldr_content") or acf.get("teaser_text")
        if not isinstance(summary, str) or not summary.strip():
            excerpt = post.get("excerpt")
            summary = excerpt.get("rendered") if isinstance(excerpt, dict) else None
        if not all(isinstance(value, str) and value.strip() for value in (title, url, summary)):
            return None

        cleaned_title = cls._clean_markup(title)
        cleaned_summary = cls._clean_markup(summary)
        relevance_text = f"{cleaned_title} {cleaned_summary}".casefold()
        if not any(term in relevance_text for term in _RELEVANT_TERMS):
            return None
        try:
            return NewsItem(
                title=cleaned_title,
                url=url.strip(),
                summary=cleaned_summary,
                published_at=post.get("date_gmt") or post.get("date"),
            )
        except ValueError:
            return None

    @staticmethod
    def _clean_markup(value: str) -> str:
        plain = _TAG_RE.sub(" ", value)
        plain = html.unescape(plain)
        return " ".join(plain.replace("**", "").split())
