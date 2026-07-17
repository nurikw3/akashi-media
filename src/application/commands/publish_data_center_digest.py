"""Command: find and immediately publish individual data-center news posts."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors import DigestCompositionError, NewsSourceError
from src.domain.models import DigestPublishReport, NewsItem, TextPublishResult
from src.domain.ports.digest_composer import DigestComposerPort
from src.domain.ports.news_source import NewsSourcePort
from src.domain.ports.text_publisher import TextPublisherPort
from src.domain.ports.digest_repository import DigestRepositoryPort

MAX_POSTS_PER_RUN = 5


@dataclass(frozen=True, slots=True)
class PublishDataCenterDigestCommand:
    news_source: NewsSourcePort
    composer: DigestComposerPort
    publisher: TextPublisherPort
    expert_source: NewsSourcePort | None = None
    digest_repository: DigestRepositoryPort | None = None

    async def execute(self, limit: int = 2, trigger: str = "manual", publish: bool = True) -> DigestPublishReport:
        if not 1 <= limit <= MAX_POSTS_PER_RUN:
            raise ValueError(f"limit must be between 1 and {MAX_POSTS_PER_RUN}")

        candidates = await self.news_source.search(limit=max(limit * 3, limit))
        selected = self._unique_items(candidates, limit)
        expert_candidates: tuple[NewsItem, ...] = ()
        if self.expert_source is not None:
            try:
                expert_candidates = await self.expert_source.search(limit=1)
            except NewsSourceError:
                # An unavailable expert source must not stop the core news digest.
                expert_candidates = ()
            selected = self._unique_items((*selected, *expert_candidates), limit + 1)
        if self.digest_repository is not None:
            if not publish:
                self.digest_repository.remember_without_publishing(selected)
                report = DigestPublishReport(len(candidates) + len(expert_candidates), 0, 0, 0)
                self.digest_repository.record_run(report, trigger)
                return report
            selected = self.digest_repository.reserve_new(selected)
        published = 0
        failed = 0

        for item in selected:
            try:
                text = await self.composer.compose(item)
            except DigestCompositionError:
                failed += 1
                if self.digest_repository is not None:
                    self.digest_repository.mark_result(item, TextPublishResult.failed("Composition failed"))
                continue

            result = await self.publisher.publish(text)
            if self.digest_repository is not None:
                self.digest_repository.mark_result(item, result)
            if result.success:
                published += 1
            else:
                failed += 1

        report = DigestPublishReport(
            candidates=len(candidates) + len(expert_candidates),
            attempted=len(selected),
            published=published,
            failed=failed,
        )
        if self.digest_repository is not None:
            self.digest_repository.record_run(report, trigger)
        return report

    @staticmethod
    def _unique_items(items: tuple[NewsItem, ...], limit: int) -> tuple[NewsItem, ...]:
        selected: list[NewsItem] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()

        for item in items:
            url_key = item.url.rstrip("/").casefold()
            title_key = " ".join(item.title.split()).casefold()
            if url_key in seen_urls or title_key in seen_titles:
                continue
            selected.append(item)
            seen_urls.add(url_key)
            seen_titles.add(title_key)
            if len(selected) == limit:
                break

        return tuple(selected)
