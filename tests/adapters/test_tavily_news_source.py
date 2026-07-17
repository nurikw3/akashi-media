import asyncio
import json

import httpx
import pytest

from src.adapters.news.tavily import TAVILY_SEARCH_URL, TavilyNewsSource
from src.domain.errors import NewsSourceError
from src.domain.ports.news_source import NewsSourcePort


def test_tavily_search_builds_scoped_news_request_and_parses_items():
    captured = {}

    async def handler(request):
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "New data center",
                        "url": "https://newsroom.equinix.com/news-releases/news-release-details/item",
                        "content": "Equinix opened a new facility.",
                        "raw_content": "Equinix opened a 20 MW facility in Madrid.",
                        "published_date": "2026-07-14",
                    },
                    {
                        "title": "Equinix blog",
                        "url": "https://blog.equinix.com/",
                        "content": "Description of the publication.",
                    },
                    {
                        "title": "Foreign result",
                        "url": "https://example.com/data-center-project",
                        "content": "Must be rejected even if Tavily returns it.",
                    },
                    {
                        "title": "Author profile",
                        "url": "https://www.datacenterdynamics.com/en/profile/editor/",
                        "content": "Not a news story.",
                    },
                    {"title": "Invalid", "url": "not-a-url", "content": "skip"},
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = TavilyNewsSource(client, "tvly-secret")
            assert isinstance(source, NewsSourcePort)
            return await source.search(6)

    items = asyncio.run(run())

    assert len(items) == 1
    assert items[0].title == "New data center"
    assert captured["authorization"] == "Bearer tvly-secret"
    assert captured["body"]["topic"] == "news"
    assert items[0].summary == "Equinix opened a 20 MW facility in Madrid."
    assert captured["body"]["time_range"] == "month"
    assert captured["body"]["max_results"] == 12
    assert "newsroom.equinix.com" in captured["body"]["include_domains"]
    assert captured["body"]["include_raw_content"] == "text"


def test_tavily_errors_are_wrapped_without_secret_detail():
    async def handler(request):
        return httpx.Response(401, json={"detail": "token tvly-secret rejected"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await TavilyNewsSource(client, "tvly-secret").search(2)

    with pytest.raises(NewsSourceError) as excinfo:
        asyncio.run(run())
    assert "tvly-secret" not in str(excinfo.value)
    assert TAVILY_SEARCH_URL.startswith("https://")


def test_tavily_enriches_missing_date_from_article_metadata():
    async def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                text='<script type="application/ld+json">'
                '{"datePublished":"2026-07-09T10:30:00Z"}</script>',
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Concrete DCD story",
                        "url": "https://www.datacenterdynamics.com/en/news/concrete-story/",
                        "content": "A concrete data center event happened.",
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await TavilyNewsSource(client, "tvly-secret").search(1)

    items = asyncio.run(run())
    assert items[0].published_at == "2026-07-09T10:30:00Z"
