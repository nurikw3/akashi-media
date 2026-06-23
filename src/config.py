"""Composition root. The ONLY place adapters are bound to ports.

Per the architecture contract, nothing else in the codebase wires concrete
implementations together — domain and application code depend on ports only,
and this module decides which adapter satisfies each port.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from src.adapters.repositories.in_memory_post_repository import InMemoryPostRepository
from src.domain.ports.content_adapter import ContentAdapterPort
from src.domain.ports.post_repository import PostRepository


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
        )


@dataclass(frozen=True, slots=True)
class Container:
    """Assembled dependencies. Feature slices add ports here as they land."""

    settings: Settings
    post_repository: PostRepository
    content_adapter: ContentAdapterPort


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
    return Container(
        settings=settings,
        post_repository=InMemoryPostRepository(),
        content_adapter=_build_content_adapter(settings),
    )


def create_app(settings: Settings | None = None):
    """Build the fully wired web application (entry point for uvicorn & tests)."""
    # Imported here to keep the composition root free of import cycles and to
    # preserve the dependency direction (config wires entrypoints, not vice versa).
    from src.entrypoints.web.app import build_web_app

    resolved = settings or Settings.from_env()
    container = build_container(resolved)
    return build_web_app(container)
