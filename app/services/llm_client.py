from __future__ import annotations

from typing import Any

import requests

from app.core.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key and not self.settings.llm_mock_mode)

    def complete(self, prompt: str, *, expect_json: bool = False) -> str:
        if not self.enabled:
            raise RuntimeError("LLM client is disabled. Configure OPENAI_API_KEY or use mock mode.")

        response = requests.post(
            f"{self.settings.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.openai_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise writing assistant. Follow formatting rules exactly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"} if expect_json else None,
            },
            timeout=self.settings.openai_request_timeout,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("No completion choices returned.")
        return choices[0]["message"]["content"]
