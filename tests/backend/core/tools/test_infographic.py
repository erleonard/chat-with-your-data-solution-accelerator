"""Tests for the AI-generated infographic painter."""

from typing import Any, Sequence

import pytest

from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.settings import ImageSize
from backend.core.tools.infographic import BRIEF_MAX_CHARS, InfographicPainter
from backend.core.types import ChatMessage, ChatRole, GeneratedImage


class _LLM:
    def __init__(self, brief: str = "Title: Plan. Section: ships in May.") -> None:
        self.brief = brief
        self.chat_messages: list[ChatMessage] = []
        self.image_calls: list[dict[str, Any]] = []

    async def chat(self, messages: Sequence[ChatMessage], **_: Any) -> ChatMessage:
        self.chat_messages = list(messages)
        return ChatMessage(role=ChatRole.ASSISTANT, content=self.brief)

    async def generate_image(self, prompt: str, **kwargs: Any) -> GeneratedImage:
        self.image_calls.append({"prompt": prompt, **kwargs})
        return GeneratedImage(b64_data="aW1n", model=kwargs["deployment"])


def _painter(llm: _LLM) -> InfographicPainter:
    return InfographicPainter(llm=llm, deployment="gpt-image-1", size=ImageSize.LANDSCAPE)  # type: ignore[arg-type]


async def test_paint_briefs_then_renders_without_citation_markers() -> None:
    llm = _LLM()
    result = await _painter(llm).paint("Ships in May [doc1] [doc2].", title="Plan")

    user = llm.chat_messages[1].content
    assert "[doc" not in user
    assert "Ships in May" in user and "Infographic title: Plan" in user
    assert "ONLY facts" in llm.chat_messages[0].content
    assert llm.image_calls == [
        {
            "prompt": "Title: Plan. Section: ships in May.",
            "deployment": "gpt-image-1",
            "size": ImageSize.LANDSCAPE,
        }
    ]
    assert result.brief == "Title: Plan. Section: ships in May."
    assert result.image.b64_data == "aW1n"


async def test_brief_is_truncated_to_budget() -> None:
    llm = _LLM(brief="x" * (BRIEF_MAX_CHARS + 50))
    brief = await _painter(llm).write_brief("text")
    assert len(brief) == BRIEF_MAX_CHARS


async def test_empty_brief_raises_before_rendering() -> None:
    llm = _LLM(brief="   ")
    with pytest.raises(ValueError):
        await _painter(llm).paint("text")
    assert llm.image_calls == []


async def test_base_provider_generate_image_is_unsupported() -> None:
    class _Bare(BaseLLMProvider):
        async def chat(self, *a: Any, **k: Any) -> ChatMessage:  # pragma: no cover
            raise AssertionError

        def chat_stream(self, *a: Any, **k: Any):  # pragma: no cover
            raise AssertionError

        async def embed(self, *a: Any, **k: Any):  # pragma: no cover
            raise AssertionError

        def reason(self, *a: Any, **k: Any):  # pragma: no cover
            raise AssertionError

    provider = _Bare(settings=None, credential=None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await provider.generate_image("draw")
