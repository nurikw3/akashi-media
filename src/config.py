"""Composition root. The ONLY place adapters are bound to ports.

Per the architecture contract, nothing else in the codebase wires concrete
implementations together — domain and application code depend on ports only,
and this module decides which adapter satisfies each port.
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.adapters.media.transient_store import TransientMediaStore
from src.adapters.publishers.factory import PublisherFactory
from src.adapters.publishers.fake import FakePublisher
from src.adapters.repositories.in_memory_digest_repository import InMemoryDigestRepository
from src.adapters.repositories.in_memory_post_repository import InMemoryPostRepository
from src.domain.models import Channel, MediaFile
from src.domain.ports.content_adapter import ContentAdapterPort
from src.domain.ports.digest_repository import DigestRepositoryPort
from src.domain.ports.post_repository import PostRepository
from src.domain.ports.publisher import PublisherPort


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration, sourced exclusively from the environment."""

    username: str
    password: str
    secret_key: str
    https_only: bool
    openai_api_key: str | None
    openai_model: str
    ig_token: str | None
    ig_user_id: str | None
    li_token: str | None
    li_author_urn: str | None
    # Public HTTPS base of this app (e.g. a tunnel in dev). Required for real
    # Instagram photo posts: Graph fetches the image from an app-served URL.
    public_base_url: str | None = None
    openai_base_url: str | None = None
    database_url: str | None = None
    buffer_api_key: str | None = None
    buffer_linkedin_channel_id: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        e = env if env is not None else os.environ

        def required(key: str) -> str:
            value = e.get(key)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {key}")
            return value

        secret_key = required("APP_SECRET_KEY")
        if len(secret_key) < 32:
            raise RuntimeError("APP_SECRET_KEY must be at least 32 characters")

        openai_model = e.get("OPENAI_MODEL") or "openai/gpt-oss-120b"
        openai_base_url = e.get("OPENAI_BASE_URL") or None
        if openai_base_url is None and openai_model.startswith("openai/"):
            openai_base_url = "https://api.groq.com/openai/v1"

        return cls(
            username=required("APP_USERNAME"),
            password=required("APP_PASSWORD"),
            secret_key=secret_key,
            https_only=(e.get("APP_HTTPS_ONLY", "false").strip().lower() in {"1", "true", "yes"}),
            openai_api_key=e.get("OPENAI_API_KEY") or None,
            openai_model=openai_model,
            ig_token=e.get("IG_TOKEN") or None,
            ig_user_id=e.get("IG_USER_ID") or None,
            li_token=e.get("LI_TOKEN") or None,
            li_author_urn=e.get("LI_AUTHOR_URN") or None,
            public_base_url=e.get("PUBLIC_BASE_URL") or None,
            openai_base_url=openai_base_url,
            database_url=e.get("DATABASE_URL") or None,
            buffer_api_key=e.get("BUFFER_API_KEY") or None,
            buffer_linkedin_channel_id=e.get("BUFFER_LINKEDIN_CHANNEL_ID") or None,
        )


@dataclass(frozen=True, slots=True)
class DigestSettings:
    """Configuration for the standalone Telegram digest process."""

    telegram_bot_token: str
    telegram_channel_id: str
    tavily_api_key: str
    openai_api_key: str
    openai_model: str = "openai/gpt-oss-120b"
    openai_base_url: str | None = "https://api.groq.com/openai/v1"
    telegram_control_chat_id: int | None = None
    post_limit: int = 2
    database_url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DigestSettings":
        e = env if env is not None else os.environ

        def required(key: str) -> str:
            value = e.get(key)
            if not value:
                raise RuntimeError(f"Missing required environment variable: {key}")
            return value

        control_chat_raw = e.get("TELEGRAM_CONTROL_CHAT_ID")
        try:
            control_chat_id = int(control_chat_raw) if control_chat_raw else None
        except ValueError as exc:
            raise RuntimeError("TELEGRAM_CONTROL_CHAT_ID must be an integer") from exc

        try:
            post_limit = int(e.get("DIGEST_POST_LIMIT", "2"))
        except ValueError as exc:
            raise RuntimeError("DIGEST_POST_LIMIT must be an integer") from exc
        if not 1 <= post_limit <= 5:
            raise RuntimeError("DIGEST_POST_LIMIT must be between 1 and 5")

        model = e.get("OPENAI_MODEL") or "openai/gpt-oss-120b"
        configured_base_url = e.get("OPENAI_BASE_URL")
        base_url = configured_base_url or (
            "https://api.groq.com/openai/v1" if model.startswith("openai/") else None
        )

        return cls(
            telegram_bot_token=required("TELEGRAM_BOT_TOKEN"),
            telegram_channel_id=required("TELEGRAM_CHANNEL_ID"),
            telegram_control_chat_id=control_chat_id,
            tavily_api_key=required("TAVILY_API_KEY"),
            openai_api_key=required("OPENAI_API_KEY"),
            openai_model=model,
            openai_base_url=base_url,
            post_limit=post_limit,
            database_url=e.get("DATABASE_URL") or None,
        )


@dataclass(frozen=True, slots=True)
class Container:
    """Assembled dependencies. Feature slices add ports here as they land."""

    settings: Settings
    post_repository: PostRepository
    content_adapter: ContentAdapterPort
    publisher_factory: PublisherFactory
    digest_repository: DigestRepositoryPort
    # Transit-only hold for media the /media route serves to the Graph API.
    media_store: "TransientMediaStore | None" = None
    # Resources (e.g. httpx clients) to close on app shutdown.
    closeables: tuple[Any, ...] = field(default=())


def _unconfigured_media_host(_media: MediaFile) -> str:
    # Phase 1 has no media hosting; the Graph API needs a public image URL.
    from src.domain.errors import PublishError

    raise PublishError("Media hosting is not configured (Phase 2)")


def _http_client():
    import httpx

    return httpx.Client(
        timeout=30.0,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )


def _build_publisher_factory(
    settings: Settings, media_store: TransientMediaStore
) -> tuple[PublisherFactory, tuple[Any, ...]]:
    """Real publishers when channel creds are present, else fakes.

    Returns the factory plus any http clients to close on shutdown.
    """
    publishers: dict[Channel, PublisherPort] = {}
    closeables: list[Any] = []

    if settings.ig_token and settings.ig_user_id:
        from src.adapters.publishers.instagram import InstagramGraphPublisher

        # Real media host when a public base URL is configured (e.g. a tunnel in
        # dev); otherwise the Phase-1 stub that reports media hosting is absent.
        if settings.public_base_url:
            from src.adapters.media.app_served_media_host import AppServedMediaHost

            resolve_image_url = AppServedMediaHost(media_store, settings.public_base_url).host
        else:
            resolve_image_url = _unconfigured_media_host

        client = _http_client()
        closeables.append(client)
        publishers[Channel.INSTAGRAM] = InstagramGraphPublisher(
            http_client=client,
            token=settings.ig_token,
            ig_user_id=settings.ig_user_id,
            resolve_image_url=resolve_image_url,
        )
    else:
        publishers[Channel.INSTAGRAM] = FakePublisher(Channel.INSTAGRAM)

    if settings.buffer_api_key and settings.buffer_linkedin_channel_id:
        from src.adapters.publishers.buffer_linkedin import BufferLinkedInPublisher

        client = _http_client()
        closeables.append(client)
        publishers[Channel.LINKEDIN] = BufferLinkedInPublisher(
            http_client=client,
            api_key=settings.buffer_api_key,
            channel_id=settings.buffer_linkedin_channel_id,
        )
    elif settings.li_token and settings.li_author_urn:
        from src.adapters.publishers.linkedin import LinkedInPublisher

        client = _http_client()
        closeables.append(client)
        publishers[Channel.LINKEDIN] = LinkedInPublisher(
            http_client=client,
            token=settings.li_token,
            author_urn=settings.li_author_urn,
        )
    else:
        publishers[Channel.LINKEDIN] = FakePublisher(Channel.LINKEDIN)

    return PublisherFactory(publishers), tuple(closeables)


def _build_content_adapter(settings: Settings) -> ContentAdapterPort:
    """OpenAI adapter when a key is present, otherwise a deterministic fake."""
    if settings.openai_api_key:
        from openai import OpenAI

        from src.adapters.content.openai_adapter import OpenAIContentAdapter

        client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        client = OpenAI(**client_kwargs)
        return OpenAIContentAdapter(client=client, model=settings.openai_model)

    from src.adapters.content.fake import FakeContentAdapter

    return FakeContentAdapter()


def build_container(settings: Settings) -> Container:
    """Bind concrete adapters to ports. Extended by each feature slice."""
    media_store = TransientMediaStore()
    publisher_factory, closeables = _build_publisher_factory(settings, media_store)
    digest_repository: DigestRepositoryPort = InMemoryDigestRepository()
    all_closeables = closeables
    if settings.database_url:
        from src.adapters.repositories.sqlalchemy_digest_repository import (
            SqlAlchemyDigestRepository,
        )

        digest_repository = SqlAlchemyDigestRepository(settings.database_url)
        all_closeables = (*closeables, digest_repository)
    return Container(
        settings=settings,
        post_repository=InMemoryPostRepository(),
        content_adapter=_build_content_adapter(settings),
        publisher_factory=publisher_factory,
        digest_repository=digest_repository,
        media_store=media_store,
        closeables=all_closeables,
    )


def create_app(settings: Settings | None = None):
    """Build the fully wired web application (entry point for uvicorn & tests)."""
    # Imported here to keep the composition root free of import cycles and to
    # preserve the dependency direction (config wires entrypoints, not vice versa).
    from src.entrypoints.web.app import build_web_app

    if settings is None:
        # Load .env on real startup only; tests inject settings and skip this.
        from dotenv import load_dotenv

        load_dotenv()
        settings = Settings.from_env()

    resolved = settings
    container = build_container(resolved)
    return build_web_app(container)


@dataclass(frozen=True, slots=True)
class DigestContainer:
    """Fully wired dependencies for the standalone Telegram entrypoint."""

    settings: DigestSettings
    bot: Any
    command: Any
    closeables: tuple[Any, ...] = field(default=())

    async def aclose(self) -> None:
        for resource in reversed(self.closeables):
            close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
            if close is None:
                continue
            result = close()
            if inspect.isawaitable(result):
                await result


def build_digest_container(settings: DigestSettings) -> DigestContainer:
    """Bind Tavily, OpenAI-compatible, and Telegram adapters to digest ports."""
    import httpx
    from aiogram import Bot
    from openai import AsyncOpenAI

    from src.adapters.content.openai_digest_composer import OpenAIDigestComposer
    from src.adapters.news.equinix_blog import EquinixBlogSource
    from src.adapters.news.tavily import TavilyNewsSource
    from src.adapters.publishers.telegram import TelegramTextPublisher
    from src.adapters.repositories.sqlalchemy_digest_repository import (
        SqlAlchemyDigestRepository,
    )
    from src.application.commands.publish_data_center_digest import (
        PublishDataCenterDigestCommand,
    )

    bot = Bot(token=settings.telegram_bot_token)
    news_client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
    )
    openai_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        openai_kwargs["base_url"] = settings.openai_base_url
    openai_client = AsyncOpenAI(**openai_kwargs)
    if not settings.database_url:
        raise RuntimeError("Missing required environment variable: DATABASE_URL")
    digest_repository = SqlAlchemyDigestRepository(settings.database_url)

    command = PublishDataCenterDigestCommand(
        news_source=TavilyNewsSource(news_client, settings.tavily_api_key),
        composer=OpenAIDigestComposer(openai_client, settings.openai_model),
        publisher=TelegramTextPublisher(bot, settings.telegram_channel_id),
        expert_source=EquinixBlogSource(news_client),
        digest_repository=digest_repository,
    )
    return DigestContainer(
        settings=settings,
        bot=bot,
        command=command,
        closeables=(news_client, openai_client, digest_repository),
    )
