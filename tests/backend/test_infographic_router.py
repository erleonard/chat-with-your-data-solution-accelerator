"""Tests for the infographic image router."""

from types import SimpleNamespace
from typing import Any, Sequence

import httpx
import pytest

from backend.app import create_app
from backend.core.settings import Environment, ImageSize
from backend.core.types import ChatMessage, ChatRole, GeneratedImage
from backend.dependencies import get_app_settings, get_llm_provider


def _settings(image_deployment: str) -> SimpleNamespace:
    return SimpleNamespace(
        environment=Environment.LOCAL,
        openai=SimpleNamespace(image_deployment=image_deployment, image_size=ImageSize.PORTRAIT),
        observability=SimpleNamespace(log_level="INFO"),
    )


class _LLM:
    async def chat(self, messages: Sequence[ChatMessage], **_: Any) -> ChatMessage:
        return ChatMessage(role=ChatRole.ASSISTANT, content="Poster: ships in May.")

    async def generate_image(self, prompt: str, **kwargs: Any) -> GeneratedImage:
        return GeneratedImage(b64_data="aW1n", model=kwargs["deployment"])


def _app(image_deployment: str):
    application = create_app()
    application.dependency_overrides[get_app_settings] = lambda: _settings(image_deployment)
    application.dependency_overrides[get_llm_provider] = lambda: _LLM()
    return application


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_returns_image_and_brief() -> None:
    async with _client(_app("gpt-image-1")) as client:
        resp = await client.post(
            "/api/infographic/image", json={"markdown": "Ships in May [doc1].", "title": "Plan"}
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "image_base64": "aW1n",
        "media_type": "image/png",
        "brief": "Poster: ships in May.",
        "ai_generated": True,
    }


async def test_returns_503_when_image_deployment_unset() -> None:
    async with _client(_app("")) as client:
        resp = await client.post("/api/infographic/image", json={"markdown": "x"})
    assert resp.status_code == 503


@pytest.mark.parametrize("payload", [{"markdown": ""}, {"markdown": "x", "extra": 1}])
async def test_rejects_invalid_payload(payload: dict[str, Any]) -> None:
    async with _client(_app("gpt-image-1")) as client:
        resp = await client.post("/api/infographic/image", json=payload)
    assert resp.status_code == 422
