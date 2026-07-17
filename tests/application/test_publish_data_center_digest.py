import asyncio

from src.application.commands.publish_data_center_digest import PublishDataCenterDigestCommand
from src.adapters.repositories.in_memory_digest_repository import InMemoryDigestRepository
from src.domain.errors import DigestCompositionError
from src.domain.models import NewsItem, TextPublishResult


def _item(title: str, url: str) -> NewsItem:
    return NewsItem(title=title, url=url, summary=f"Summary for {title}")


class _Source:
    def __init__(self, items):
        self.items = tuple(items)
        self.requested_limit = None

    async def search(self, limit):
        self.requested_limit = limit
        return self.items


class _Composer:
    def __init__(self, failing_title=None):
        self.failing_title = failing_title
        self.items = []

    async def compose(self, item):
        self.items.append(item)
        if item.title == self.failing_title:
            raise DigestCompositionError("failed")
        return f"Post: {item.title}"


class _Publisher:
    def __init__(self, fail_text=None):
        self.fail_text = fail_text
        self.texts = []

    async def publish(self, text):
        self.texts.append(text)
        if text == self.fail_text:
            return TextPublishResult.failed("failed")
        return TextPublishResult.ok(str(len(self.texts)))


def test_command_deduplicates_and_publishes_two_individual_posts():
    source = _Source(
        [
            _item("Equinix update", "https://example.com/a"),
            _item("Equinix update", "https://example.com/duplicate-title"),
            _item("Cooling news", "https://example.com/b"),
            _item("Power news", "https://example.com/c"),
        ]
    )
    composer = _Composer()
    publisher = _Publisher()
    command = PublishDataCenterDigestCommand(source, composer, publisher)

    report = asyncio.run(command.execute(limit=2))

    assert source.requested_limit == 6
    assert [item.title for item in composer.items] == ["Equinix update", "Cooling news"]
    assert publisher.texts == ["Post: Equinix update", "Post: Cooling news"]
    assert report.published == 2
    assert report.failed == 0
    assert report.attempted == 2


def test_command_continues_after_composition_and_publish_failures():
    source = _Source(
        [
            _item("Bad compose", "https://example.com/a"),
            _item("Bad publish", "https://example.com/b"),
        ]
    )
    composer = _Composer(failing_title="Bad compose")
    publisher = _Publisher(fail_text="Post: Bad publish")
    repository = InMemoryDigestRepository()
    command = PublishDataCenterDigestCommand(source, composer, publisher, digest_repository=repository)

    report = asyncio.run(command.execute(limit=2))

    assert report.published == 0
    assert report.failed == 2
    assert {item.status for item in repository.dashboard().publications} == {"failed"}
    assert report.attempted == 2


def test_command_rejects_unsafe_limit():
    command = PublishDataCenterDigestCommand(_Source([]), _Composer(), _Publisher())

    try:
        asyncio.run(command.execute(limit=6))
    except ValueError as exc:
        assert "between 1 and 5" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_command_adds_one_expert_post_after_the_industry_digest():
    source = _Source(
        [
            _item("Industry one", "https://example.com/a"),
            _item("Industry two", "https://example.com/b"),
        ]
    )
    expert = _Source([_item("Equinix expert view", "https://example.com/equinix")])
    composer = _Composer()
    publisher = _Publisher()
    command = PublishDataCenterDigestCommand(source, composer, publisher, expert_source=expert)

    report = asyncio.run(command.execute(limit=2))

    assert expert.requested_limit == 1
    assert [item.title for item in composer.items] == [
        "Industry one",
        "Industry two",
        "Equinix expert view",
    ]
    assert report.candidates == 3
    assert report.published == 3


def test_command_remembers_baseline_and_never_republishes_same_url():
    source = _Source([_item("Industry one", "https://example.com/a")])
    composer = _Composer()
    publisher = _Publisher()
    repository = InMemoryDigestRepository()
    command = PublishDataCenterDigestCommand(source, composer, publisher, digest_repository=repository)

    baseline = asyncio.run(command.execute(limit=1, trigger="baseline", publish=False))
    repeated = asyncio.run(command.execute(limit=1, trigger="scheduled"))

    assert baseline.attempted == 0
    assert repeated.attempted == 0
    assert publisher.texts == []
    dashboard = repository.dashboard()
    assert dashboard.last_run is not None
    assert dashboard.last_run.trigger == "scheduled"
    assert dashboard.publications[0].status == "baseline"


def test_command_persists_manual_publication_and_deduplicates_next_run():
    source = _Source([_item("Industry one", "https://example.com/a")])
    publisher = _Publisher()
    repository = InMemoryDigestRepository()
    command = PublishDataCenterDigestCommand(source, _Composer(), publisher, digest_repository=repository)

    first = asyncio.run(command.execute(limit=1))
    second = asyncio.run(command.execute(limit=1))

    assert first.published == 1
    assert second.attempted == 0
    assert len(publisher.texts) == 1
    assert repository.dashboard().total_published == 1
