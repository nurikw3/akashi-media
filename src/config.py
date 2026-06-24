"""Composition root. The ONLY place adapters are bound to ports.

Per the architecture contract, nothing else in the codebase wires concrete
implementations together — domain and application code depend on ports only,
and this module decides which adapter satisfies each port.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.adapters.media.transient_store import TransientMediaStore
from src.adapters.publishers.factory import PublisherFactory
from src.adapters.publishers.fake import FakePublisher
from src.adapters.repositories.in_memory_post_repository import InMemoryPostRepository
from src.domain.models import Channel, MediaFile
from src.domain.ports.content_adapter import ContentAdapterPort
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

        return cls(
            username=required("APP_USERNAME"),
            password=required("APP_PASSWORD"),
            secret_key=secret_key,
            https_only=(e.get("APP_HTTPS_ONLY", "false").strip().lower() in {"1", "true", "yes"}),
            openai_api_key=e.get("OPENAI_API_KEY") or None,
            openai_model=e.get("OPENAI_MODEL") or "gpt-4o-mini",
            ig_token=e.get("IG_TOKEN") or None,
            ig_user_id=e.get("IG_USER_ID") or None,
            li_token=e.get("LI_TOKEN") or None,
            li_author_urn=e.get("LI_AUTHOR_URN") or None,
            public_base_url=e.get("PUBLIC_BASE_URL") or None,
        )


@dataclass(frozen=True, slots=True)
class Container:
    """Assembled dependencies. Feature slices add ports here as they land."""

    settings: Settings
    post_repository: PostRepository
    content_adapter: ContentAdapterPort
    publisher_factory: PublisherFactory
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

    if settings.li_token and settings.li_author_urn:
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

        client = OpenAI(api_key=settings.openai_api_key)
        return OpenAIContentAdapter(client=client, model=settings.openai_model)

    from src.adapters.content.fake import FakeContentAdapter

    return FakeContentAdapter()


def build_container(settings: Settings) -> Container:
    """Bind concrete adapters to ports. Extended by each feature slice."""
    media_store = TransientMediaStore()
    publisher_factory, closeables = _build_publisher_factory(settings, media_store)
    return Container(
        settings=settings,
        post_repository=InMemoryPostRepository(),
        content_adapter=_build_content_adapter(settings),
        publisher_factory=publisher_factory,
        media_store=media_store,
        closeables=closeables,
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
