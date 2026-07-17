import asyncio
import json

import httpx

from src.adapters.news.equinix_blog import EquinixBlogSource
from src.domain.ports.news_source import NewsSourcePort


def test_equinix_source_uses_latest_relevant_wordpress_article():
    posts = [
        {
            "date_gmt": "2026-07-11T11:55:00",
            "link": "https://blog.equinix.com/blog/2026/07/11/partner-news/",
            "title": {"rendered": "Partner news"},
            "excerpt": {"rendered": "General business update."},
            "acf": {},
        },
        {
            "date_gmt": "2026-07-09T11:55:02",
            "link": (
                "https://blog.equinix.com/blog/2026/07/09/"
                "could-data-centers-be-the-low-carbon-heat-source-that-communities-need/"
            ),
            "title": {"rendered": "Could <em>Data Centers</em> Heat Communities?"},
            "acf": {
                "tldr_content": (
                    "<ul><li>Data center heat export reuses residual server heat.</li>"
                    "<li>Equinix and A2A are working in Milan.</li></ul>"
                )
            },
        },
    ]
    body = f"Title: Equinix\n\nMarkdown Content:\n{json.dumps(posts)}\n"

    async def handler(request):
        assert "wp-json/wp/v2/posts" in str(request.url)
        return httpx.Response(200, text=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = EquinixBlogSource(client)
            assert isinstance(source, NewsSourcePort)
            return await source.search(1)

    items = asyncio.run(run())

    assert len(items) == 1
    assert items[0].title == "Could Data Centers Heat Communities?"
    assert "residual server heat" in items[0].summary
    assert items[0].published_at == "2026-07-09T11:55:02"
