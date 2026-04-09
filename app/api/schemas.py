from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenTiers(BaseModel):
    standard: bool
    vip: bool


class HealthData(BaseModel):
    status: str
    llm_enabled: bool
    mock_mode: bool
    image_generation_enabled: bool
    image_generation_mode: str
    token_protection_enabled: bool
    token_tiers: TokenTiers


class HealthResponse(BaseModel):
    success: bool = True
    data: HealthData


class TaskCreateRequest(BaseModel):
    token: str = ""
    category: str = Field(..., examples=["seo"])
    keywords: list[str] | str = Field(
        ...,
        examples=[["portable charger on plane", "tsa power bank rules"]],
    )
    info: str = ""
    brand_info: str = ""
    language: str = "English"
    force_refresh: bool = False
    generate_images: bool = True

    model_config = {
        "json_schema_extra": {
            "example": {
                "token": "demo-vip-token",
                "category": "seo",
                "keywords": ["portable charger on plane", "tsa power bank rules"],
                "info": "Brand: VoltGo. Product: 20000mAh portable charger.",
                "language": "English",
                "force_refresh": False,
                "generate_images": True,
            }
        }
    }


class TaskAcceptedData(BaseModel):
    task_id: str
    status: str
    access_tier: str


class TaskCreateResponse(BaseModel):
    success: bool = True
    data: TaskAcceptedData


class TaskDetailResponse(BaseModel):
    success: bool = True
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
