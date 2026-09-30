"""Tests for the synthesis router."""

from types import SimpleNamespace
from typing import Any, Sequence

import httpx
import pytest

from backend.app import create_app
from backend.core.settings import Environment
from backend.core.types import ChatMessage, ChatRole, Conversation, MessageRecord, SearchResult
from backend.dependencies import (
    get_app_settings,
    get_content_safety_guard,
    get_database_client,
    get_llm_provider,
    get_search_provider,
)
from backend.models.synthesize import SynthesisRequest
from backend.services.synthesize import synthesis_question


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        environment=Environment.LOCAL,
        orchestrator=SimpleNamespace(name="langgraph", agent_id=""),
        openai=SimpleNamespace(
            temperature=0.0,
            max_tokens=1000,
            synthesis_max_tokens=4000,
            synthesis_batch_chars=24000,
        ),
        search=SimpleNamespace(use_semantic_search=True, top_k=5),
        observability=SimpleNamespace(log_level="INFO"),
        content_safety=SimpleNamespace(enabled=False),
        database=SimpleNamespace(index_store="AzureSearch"),
    )


class _Search:
    async def list_chunks(self, source: str) -> list[SearchResult]:
        return [SearchResult(id=f"{source}-0", content="The project ships in May.", title=source)]


class _LLM:
    async def chat(self, messages: Sequence[ChatMessage], **_: Any) -> ChatMessage:
        return ChatMessage(role=ChatRole.ASSISTANT, content="It ships in May [doc1].")


class _DB:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.added: list[ChatMessage] = []

    async def get_conversation(self, conversation_id: str, user_id: str) -> Conversation | None:
        return None

    async def create_conversation(self, user_id: str, title: str) -> Conversation:
        self.created.append(title)
        return Conversation(id="conv-new", user_id=user_id, title=title)

    async def add_message(self, conversation_id: str, user_id: str, message: ChatMessage) -> MessageRecord:
        self.added.append(message)
        return MessageRecord(
            id=f"m{len(self.added)}",
            conversation_id=conversation_id,
            role=message.role,
            content=message.content,
        )


class _Verdict:
    flagged = True
    triggered = ["hate"]


class _Guard:
    async def screen(self, text: str) -> _Verdict:
        return _Verdict()


@pytest.fixture
def db() -> _DB:
    return _DB()


@pytest.fixture
def app(db: _DB):
    application = create_app()
    application.dependency_overrides[get_app_settings] = _settings
    application.dependency_overrides[get_llm_provider] = lambda: _LLM()
    application.dependency_overrides[get_search_provider] = lambda: _Search()
    application.dependency_overrides[get_database_client] = lambda: db
    application.dependency_overrides[get_content_safety_guard] = lambda: None
    return application


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_buffered_synthesis_returns_cited_answer_and_persists(app, db: _DB) -> None:
    async with _client(app) as client:
        resp = await client.post("/api/synthesize", json={"document_sources": ["plan.pdf"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == "It ships in May [doc1]."
    assert [c["id"] for c in body["citations"]] == ["[doc1]"]
    assert body["conversation_id"] == "conv-new"
    assert db.created and "plan.pdf" in db.created[0]


async def test_streaming_synthesis_emits_sse_channels(app) -> None:
    async with _client(app) as client:
        resp = await client.post(
            "/api/synthesize",
            json={"document_sources": ["plan.pdf"]},
            headers={"Accept": "text/event-stream"},
        )
    assert resp.status_code == 200
    text = resp.text
    for channel in ("reasoning", "citation", "answer"):
        assert f"event: {channel}" in text


async def test_requires_at_least_one_source(app) -> None:
    async with _client(app) as client:
        resp = await client.post("/api/synthesize", json={"document_sources": []})
    assert resp.status_code == 422


async def test_without_search_backend_returns_503(app) -> None:
    app.dependency_overrides[get_search_provider] = lambda: None
    async with _client(app) as client:
        resp = await client.post("/api/synthesize", json={"document_sources": ["a.pdf"]})
    assert resp.status_code == 503


async def test_flagged_instructions_are_blocked(app) -> None:
    app.dependency_overrides[get_content_safety_guard] = lambda: _Guard()
    async with _client(app) as client:
        resp = await client.post(
            "/api/synthesize",
            json={"document_sources": ["a.pdf"], "instructions": "bad"},
            headers={"Accept": "text/event-stream"},
        )
    assert "event: error" in resp.text
    assert "event: answer" not in resp.text


def test_synthesis_question_includes_sources_and_focus() -> None:
    q = synthesis_question(
        SynthesisRequest(document_sources=["a.pdf", "b.docx"], instructions=" execs ")
    )
    assert q == "Synthesize project documentation from: a.pdf, b.docx\n\nFocus: execs"


def test_synthesis_question_labels_infographic() -> None:
    q = synthesis_question(
        SynthesisRequest(document_sources=["a.pdf"], format="infographic")  # type: ignore[arg-type]
    )
    assert q == "Synthesize an infographic from: a.pdf"
