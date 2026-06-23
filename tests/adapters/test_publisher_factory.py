import pytest

from src.adapters.publishers.factory import PublisherFactory
from src.adapters.publishers.fake import FakePublisher
from src.domain.errors import UnknownChannelError
from src.domain.models import Channel


def test_create_returns_registered_publisher_by_enum():
    ig = FakePublisher(Channel.INSTAGRAM)
    factory = PublisherFactory({Channel.INSTAGRAM: ig})
    assert factory.create(Channel.INSTAGRAM) is ig


def test_create_selects_by_string():
    ig = FakePublisher(Channel.INSTAGRAM)
    factory = PublisherFactory({Channel.INSTAGRAM: ig})
    assert factory.create("instagram") is ig


def test_create_unknown_string_raises_unknown_channel():
    factory = PublisherFactory({Channel.INSTAGRAM: FakePublisher(Channel.INSTAGRAM)})
    with pytest.raises(UnknownChannelError):
        factory.create("tiktok")


def test_create_unregistered_channel_raises_unknown_channel():
    factory = PublisherFactory({Channel.INSTAGRAM: FakePublisher(Channel.INSTAGRAM)})
    with pytest.raises(UnknownChannelError):
        factory.create(Channel.LINKEDIN)


def test_fake_publisher_satisfies_port():
    from src.domain.ports.publisher import PublisherPort

    assert isinstance(FakePublisher(Channel.INSTAGRAM), PublisherPort)
