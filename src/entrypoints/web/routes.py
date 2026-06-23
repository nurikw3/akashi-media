"""Public + authenticated page routes for the composer shell.

Feature slices (S1 repackage, S2/S3 publish) attach their htmx endpoints to
this router. S0 ships the health check and the login-gated main page.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.application.commands.publish_post import PublishPostCommand
from src.application.commands.repackage_for_linkedin import RepackageForLinkedInCommand
from src.domain.errors import ContentAdaptationError
from src.domain.models import Channel, MediaFile
from src.entrypoints.web.auth import require_user

MAX_MEDIA_BYTES = 8 * 1024 * 1024  # 8 MB

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

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "index.html", {"user": user})

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

    @router.post("/publish/instagram", response_class=HTMLResponse)
    def publish_instagram(
        request: Request,
        source_text: str = Form(..., max_length=20_000),
        media: UploadFile = File(...),
        user: str = Depends(require_user),
    ):
        container = request.app.state.container
        try:
            media_file = _read_media(media)
        except ValueError as exc:
            return templates.TemplateResponse(
                request, "partials/publish_result.html", {"result": None, "error": str(exc)}
            )

        publisher = container.publisher_factory.create(Channel.INSTAGRAM)
        command = PublishPostCommand(
            publisher=publisher, post_repository=container.post_repository
        )
        result = command.execute(source_text, media_file)
        return templates.TemplateResponse(
            request, "partials/publish_result.html", {"result": result, "error": None}
        )

    app.include_router(router)
