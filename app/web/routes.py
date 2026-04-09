from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse

from app.core.runtime import AppServices
from app.web.context import build_demo_page_context


def create_web_router(services: AppServices) -> APIRouter:
    router = APIRouter(tags=["web"])

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        context = build_demo_page_context(
            llm_enabled=services.writer_service.llm_client.enabled,
            image_enabled=services.image_service.enabled,
            image_mode=services.image_service.mode,
        )
        context["request"] = request
        return services.templates.TemplateResponse(request, "demo/index.html", context)

    @router.get("/generated/{asset_namespace}/{filename:path}", tags=["assets"])
    async def serve_generated_asset(asset_namespace: str, filename: str) -> FileResponse:
        base_dir = services.settings.image_dir.resolve()
        asset_path = (base_dir / asset_namespace / filename).resolve()
        if not str(asset_path).startswith(str(base_dir)) or not asset_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
        return FileResponse(asset_path)

    return router
