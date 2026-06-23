from src.adapters.publishers.fake import FakePublisher
from src.adapters.repositories.in_memory_post_repository import InMemoryPostRepository
from src.application.commands.publish_post import PublishPostCommand
from src.domain.models import Channel, MediaFile

MEDIA = MediaFile(filename="p.jpg", content_type="image/jpeg", data=b"\xff\xd8\xff")


def _command(publisher):
    repo = InMemoryPostRepository()
    return PublishPostCommand(publisher=publisher, post_repository=repo), repo


def test_publish_delegates_to_publisher_and_records():
    publisher = FakePublisher(Channel.INSTAGRAM)
    command, repo = _command(publisher)

    result = command.execute("caption", MEDIA)

    assert result.success is True
    assert publisher.published == [("caption", MEDIA)]
    assert repo.all() == [result]


def test_publish_records_failures_too():
    publisher = FakePublisher(Channel.INSTAGRAM, succeed=False)
    command, repo = _command(publisher)

    result = command.execute("caption", MEDIA)

    assert result.success is False
    assert repo.all() == [result]
