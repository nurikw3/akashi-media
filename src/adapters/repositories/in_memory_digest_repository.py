from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import urlparse

from src.domain.models import DigestDashboard, DigestPublication, DigestPublishReport, DigestRun, NewsItem, TextPublishResult


def _source_name(url: str) -> str:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    return {"datacenterdynamics.com": "Data Center Dynamics", "blog.equinix.com": "Equinix Blog"}.get(host, host)


class InMemoryDigestRepository:
    def __init__(self) -> None:
        self._items: dict[str, DigestPublication] = {}
        self._runs: list[DigestRun] = []

    def reserve_new(self, items: tuple[NewsItem, ...]) -> tuple[NewsItem, ...]:
        reserved = []
        now = datetime.now(UTC)
        for item in items:
            if item.url in self._items:
                continue
            self._items[item.url] = DigestPublication(item.title, _source_name(item.url), item.url, item.published_at, "pending", None, now, None)
            reserved.append(item)
        return tuple(reserved)

    def mark_result(self, item: NewsItem, result: TextPublishResult) -> None:
        record = self._items[item.url]
        now = datetime.now(UTC)
        self._items[item.url] = replace(record, status="published" if result.success else "failed", telegram_message_id=result.external_id, published_at=now if result.success else None)

    def remember_without_publishing(self, items: tuple[NewsItem, ...]) -> None:
        for item in self.reserve_new(items):
            record = self._items[item.url]
            self._items[item.url] = replace(record, status="baseline")

    def record_run(self, report: DigestPublishReport, trigger: str) -> None:
        now = datetime.now(UTC)
        self._runs.append(DigestRun(trigger, report.candidates, report.attempted, report.published, report.failed, now, now))

    def has_runs(self) -> bool:
        return bool(self._runs)

    def dashboard(self, limit: int = 20) -> DigestDashboard:
        now = datetime.now(UTC)
        values = tuple(sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)[:limit])
        published = [item for item in self._items.values() if item.status == "published"]
        published_today = sum(
            1
            for item in published
            if item.published_at is not None and item.published_at.date() == now.date()
        )
        return DigestDashboard(
            len(published),
            published_today,
            self._runs[-1] if self._runs else None,
            values,
        )
