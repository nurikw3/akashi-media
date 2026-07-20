"""Public + authenticated page routes for the composer shell.

Feature slices (S1 repackage, S2/S3 publish) attach their htmx endpoints to
this router. S0 ships the health check and the login-gated main page.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from src.application.commands.publish_post import PublishPostCommand
from src.application.commands.generate_akashi_content import GenerateAkashiContentCommand
from src.application.commands.repackage_for_linkedin import RepackageForLinkedInCommand
from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel, ContentTask, MediaFile
from src.entrypoints.web.auth import require_user

MAX_MEDIA_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_MEDIA_FILES = 10
MAX_TOTAL_MEDIA_BYTES = 64 * 1024 * 1024

# Magic-byte signatures — defend against a forged Content-Type header.
_MEDIA_MAGIC: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
    "image/gif": (b"GIF87a", b"GIF89a"),
}


def _verify_magic(data: bytes, content_type: str) -> None:
    signatures = _MEDIA_MAGIC.get(content_type, ())
    if not signatures or not any(data.startswith(sig) for sig in signatures):
        raise ValueError("Содержимое файла не соответствует типу изображения")


def _read_media(upload: UploadFile) -> MediaFile:
    """Read an upload into a domain MediaFile with a hard size cap and checks."""
    data = upload.file.read(MAX_MEDIA_BYTES + 1)
    if len(data) > MAX_MEDIA_BYTES:
        raise ValueError("Файл слишком большой (макс. 8 МБ)")
    content_type = upload.content_type or "application/octet-stream"
    # Verify the bytes match the declared image type (header can be forged).
    _verify_magic(data, content_type)
    # Strip any path components from the client-supplied filename.
    filename = os.path.basename(upload.filename or "upload") or "upload"
    # MediaFile re-validates the content-type allowlist and non-empty data.
    return MediaFile(filename=filename, content_type=content_type, data=data)


def register_routes(app: FastAPI, templates: Jinja2Templates) -> None:
    router = APIRouter()

    @router.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # Public, unauthenticated: the Instagram Graph API fetches the image here
    # server-side, so it cannot present a session cookie. The token is an
    # unguessable handle into the transient store, valid only briefly.
    @router.head("/media/{token}")
    @router.get("/media/{token}")
    async def media(request: Request, token: str) -> Response:
        store = request.app.state.container.media_store
        media_file = store.get(token) if store is not None else None
        if media_file is None:
            return Response(status_code=404)
        return Response(
            content=b"" if request.method == "HEAD" else media_file.data,
            media_type=media_file.content_type,
            headers={
                "Cache-Control": "private, max-age=600",
                "Content-Length": str(len(media_file.data)),
            },
        )

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "index.html", {"user": user})

    @router.get("/digest", response_class=HTMLResponse)
    async def digest(request: Request, user: str = Depends(require_user)):
        dashboard = request.app.state.container.digest_repository.dashboard()
        return templates.TemplateResponse(
            request,
            "digest.html",
            {"user": user, "dashboard": dashboard},
        )

    @router.get("/digest/partial", response_class=HTMLResponse)
    async def digest_partial(request: Request, user: str = Depends(require_user)):
        dashboard = request.app.state.container.digest_repository.dashboard()
        return templates.TemplateResponse(
            request,
            "partials/digest_dashboard.html",
            {"dashboard": dashboard},
        )

    # Sync def: the LLM call is blocking I/O, so Starlette runs it in a
    # threadpool instead of stalling the event loop.
    @router.post("/repackage/linkedin", response_class=HTMLResponse)
    def repackage_linkedin(
        request: Request,
        source_text: str = Form(..., max_length=20_000),  # coarse DoS guard; command caps further
        user: str = Depends(require_user),
    ):
        command = RepackageForLinkedInCommand(request.app.state.container.content_adapter)
        try:
            adapted = command.execute(source_text)
        except ContentAdaptationError:
            return templates.TemplateResponse(
                request,
                "partials/linkedin_adapted.html",
                {"adapted_text": None, "error": "Не удалось адаптировать текст. Попробуйте ещё раз."},
            )
        return templates.TemplateResponse(
            request,
            "partials/linkedin_adapted.html",
            {"adapted_text": adapted, "error": None},
        )

    @router.post("/content/generate", response_class=HTMLResponse)
    def generate_content(
        request: Request,
        task: str = Form(...),
        brief: str = Form(..., max_length=20_000),
        user: str = Depends(require_user),
    ):
        try:
            resolved_task = ContentTask(task)
            generated = GenerateAkashiContentCommand(
                request.app.state.container.content_adapter
            ).execute(resolved_task, brief)
        except ValueError:
            return templates.TemplateResponse(
                request,
                "partials/ai_content_result.html",
                {"generated": None, "error": "Неизвестный сценарий генерации. Обновите страницу и попробуйте ещё раз."},
            )
        except ContentAdaptationError:
            return templates.TemplateResponse(
                request,
                "partials/ai_content_result.html",
                {"generated": None, "error": "Не удалось связаться с OpenAI. Повторите запрос через несколько секунд."},
            )
        return templates.TemplateResponse(
            request,
            "partials/ai_content_result.html",
            {"generated": generated, "error": None},
        )

    def _publish(request: Request, channel: Channel, text: str, media: list[UploadFile] | None):
        """Shared publish flow for both channels: validate → command → fragment."""
        container = request.app.state.container

        def fragment(result, error):
            return templates.TemplateResponse(
                request, "partials/publish_result.html", {"result": result, "error": error}
            )

        clean_text = text.strip()
        if not clean_text:
            return fragment(None, "Текст публикации пуст")
        if not media:
            raise HTTPException(status_code=422, detail="Фото обязательно для этого канала")
        if len(media) > MAX_MEDIA_FILES:
            return fragment(None, f"Можно выбрать не более {MAX_MEDIA_FILES} фото")
        try:
            media_files = tuple(_read_media(upload) for upload in media)
            if sum(len(item.data) for item in media_files) > MAX_TOTAL_MEDIA_BYTES:
                return fragment(None, "Общий размер фотографий не должен превышать 64 МБ")
            if channel is Channel.LINKEDIN:
                if container.media_converter is None:
                    raise ValueError("PDF-конвертер не настроен")
                publish_media = (
                    container.media_converter.images_to_pdf(media_files),
                    media_files[0],
                )
            else:
                publish_media = media_files
        except ValueError as exc:
            return fragment(None, str(exc))

        publisher = container.publisher_factory.create(channel)
        command = PublishPostCommand(
            publisher=publisher, post_repository=container.post_repository
        )
        return fragment(command.execute(clean_text, publish_media), None)

    @router.post("/publish/instagram", response_class=HTMLResponse)
    def publish_instagram(
        request: Request,
        source_text: str = Form(..., max_length=20_000),
        media: list[UploadFile] = File(...),
        user: str = Depends(require_user),
    ):
        return _publish(request, Channel.INSTAGRAM, source_text, media)

    @router.post("/publish/linkedin", response_class=HTMLResponse)
    def publish_linkedin(
        request: Request,
        linkedin_text: str = Form(..., max_length=20_000),
        media: list[UploadFile] | None = File(default=None),
        user: str = Depends(require_user),
    ):
        return _publish(request, Channel.LINKEDIN, linkedin_text, media)

    app.include_router(router)
