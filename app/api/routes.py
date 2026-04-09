from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.runtime import AppServices
from app.utils.common import split_keywords
from .schemas import (
    ErrorResponse,
    HealthData,
    HealthResponse,
    TaskAcceptedData,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskDetailResponse,
    TokenTiers,
)


def resolve_access_tier(services: AppServices, token: str) -> str | None:
    token = token.strip()
    if not token:
        return None
    if services.settings.vip_access_token and token == services.settings.vip_access_token:
        return "vip"
    if services.settings.normal_access_token and token == services.settings.normal_access_token:
        return "standard"
    return None


def create_api_router(services: AppServices) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["api"])

    @router.get(
        "/health",
        response_model=HealthResponse,
        responses={200: {"model": HealthResponse}},
        summary="Check service status",
    )
    async def health() -> HealthResponse:
        return HealthResponse(
            data=HealthData(
                status="ok",
                llm_enabled=services.writer_service.llm_client.enabled,
                mock_mode=not services.writer_service.llm_client.enabled,
                image_generation_enabled=services.image_service.enabled,
                image_generation_mode=services.image_service.mode,
                token_protection_enabled=bool(
                    services.settings.normal_access_token or services.settings.vip_access_token
                ),
                token_tiers=TokenTiers(
                    standard=bool(services.settings.normal_access_token),
                    vip=bool(services.settings.vip_access_token),
                ),
            )
        )

    @router.post(
        "/tasks",
        response_model=TaskCreateResponse,
        responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
        summary="Create an async article generation task",
    )
    async def create_task(payload: TaskCreateRequest) -> TaskCreateResponse | JSONResponse:
        category = payload.category.strip().lower()
        info = (payload.info or payload.brand_info or "").strip()
        language = (payload.language or "English").strip() or "English"
        access_tier = resolve_access_tier(services, payload.token)

        if category not in {"seo", "geo"}:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "category must be seo or geo"},
            )

        if not access_tier:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"success": False, "message": "valid access token is required"},
            )

        keywords = split_keywords(payload.keywords)
        if not keywords:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "message": "keywords is required"},
            )

        task = services.task_service.create_task(
            category=category,
            keywords=keywords,
            info=info,
            language=language,
            force_refresh=payload.force_refresh,
            generate_images=payload.generate_images,
            access_tier=access_tier,
        )
        return TaskCreateResponse(
            data=TaskAcceptedData(
                task_id=task["task_id"],
                status=task["status"],
                access_tier=access_tier,
            )
        )

    @router.get(
        "/tasks/{task_id}",
        response_model=TaskDetailResponse,
        responses={404: {"model": ErrorResponse}},
        summary="Fetch an async task result",
    )
    async def get_task(task_id: str) -> TaskDetailResponse | JSONResponse:
        task = services.task_service.get_task(task_id)
        if not task:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"success": False, "message": "task not found"},
            )
        return TaskDetailResponse(data=task)

    return router
