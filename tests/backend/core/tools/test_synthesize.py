"""Tests for the whole-document synthesis tool."""

import re
from typing import Any, Sequence

from backend.core.tools.synthesize import (
    NO_CONTENT_MESSAGE,
    DocumentSynthesizer,
    SynthesisFormat,
    build_batches,
    group_notes,
)
from backend.core.types import (
    ChatMessage,
    ChatRole,
    OrchestratorChannel,
    OrchestratorEvent,
    SearchResult,
)


def _chunk(source: str, index: int, text: str) -> SearchResult:
    return SearchResult(id=f"{source}-{index}", content=text, title=source)


class _FakeSearch:
    def __init__(self, docs: dict[str, list[SearchResult]]) -> None:
        self._docs = docs
        self.listed: list[str] = []

    async def list_chunks(self, source: str) -> list[SearchResult]:
        self.listed.append(source)
        return self._docs.get(source, [])


class _FakeLLM:
    """Echoes the first [docN] marker of each prompt so citations flow through."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[ChatMessage], dict[str, Any]]] = []

    async def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatMessage:
        self.calls.append((list(messages), kwargs))
        markers = re.findall(r"\[doc\d+\]", messages[-1].content)
        body = " ".join(f"Fact {m}." for m in dict.fromkeys(markers))
        return ChatMessage(role=ChatRole.ASSISTANT, content=body or "nothing")


async def _drain(synth: DocumentSynthesizer, sources: list[str], **kwargs: Any) -> list[OrchestratorEvent]:
    return [event async for event in synth.run(sources, **kwargs)]


def test_build_batches_respects_budget_and_global_start() -> None:
    chunks = [_chunk("a", i, "x" * 10) for i in range(5)]
    batches = build_batches(chunks, max_chars=25)
    assert [b.start for b in batches] == [1, 3, 5]
    assert [len(b.chunks) for b in batches] == [2, 2, 1]


def test_build_batches_keeps_oversized_chunk_whole() -> None:
    chunks = [_chunk("a", 0, "x" * 100), _chunk("a", 1, "y")]
    batches = build_batches(chunks, max_chars=10)
    assert [len(b.chunks) for b in batches] == [1, 1]
    assert batches[0].chunks[0].content == "x" * 100


def test_group_notes_packs_consecutively() -> None:
    assert group_notes(["aa", "bb", "cc"], max_chars=4) == [["aa", "bb"], ["cc"]]


async def test_run_reads_every_source_and_cites_globally() -> None:
    search = _FakeSearch(
        {
            "a.pdf": [_chunk("a.pdf", i, f"page {i}") for i in range(3)],
            "b.docx": [_chunk("b.docx", 0, "para")],
        }
    )
    llm = _FakeLLM()
    synth = DocumentSynthesizer(llm=llm, search=search, max_tokens=4000, batch_chars=12)  # type: ignore[arg-type]

    events = await _drain(synth, ["a.pdf", "b.docx"], instructions="for executives")

    assert search.listed == ["a.pdf", "b.docx"]
    channels = [e.channel for e in events]
    assert channels[-1] == OrchestratorChannel.ANSWER
    assert OrchestratorChannel.REASONING in channels
    citations = [e.metadata for e in events if e.channel == OrchestratorChannel.CITATION]
    answer = events[-1].content
    # All four chunks were referenced and renumbered sequentially.
    assert [c["id"] for c in citations] == ["[doc1]", "[doc2]", "[doc3]", "[doc4]"]
    assert {c["metadata"]["source_id"] for c in citations} == {
        "a.pdf-0", "a.pdf-1", "a.pdf-2", "b.docx-0"
    }
    assert "[doc4]" in answer
    # Map calls used offset markers beyond the first batch.
    map_prompts = [m[-1].content for m, _ in llm.calls[:-1]]
    assert any("[doc3]:" in p for p in map_prompts)
    # Every call is grounded by the shared guardrail, honors the budget, and carries focus.
    for messages, kwargs in llm.calls:
        assert "Fixed safety and grounding rules" in messages[0].content
        assert kwargs["max_tokens"] == 4000
        assert "for executives" in messages[-1].content
    assert "Executive summary" in llm.calls[-1][0][0].content


async def test_run_with_no_content_answers_without_llm() -> None:
    llm = _FakeLLM()
    synth = DocumentSynthesizer(llm=llm, search=_FakeSearch({}), max_tokens=10, batch_chars=10)  # type: ignore[arg-type]
    events = await _drain(synth, ["missing.pdf"], synthesis_format=SynthesisFormat.PROJECT_DOCUMENTATION)
    assert events[-1].channel == OrchestratorChannel.ANSWER
    assert events[-1].content == NO_CONTENT_MESSAGE
    assert llm.calls == []


async def test_run_condenses_notes_that_exceed_budget() -> None:
    search = _FakeSearch({"a.pdf": [_chunk("a.pdf", i, "p" * 20) for i in range(6)]})
    llm = _FakeLLM()
    synth = DocumentSynthesizer(llm=llm, search=search, max_tokens=100, batch_chars=20)  # type: ignore[arg-type]
    events = await _drain(synth, ["a.pdf"])
    reasoning = [e.content for e in events if e.channel == OrchestratorChannel.REASONING]
    assert any(r.startswith("Consolidating") for r in reasoning)
    assert events[-1].channel == OrchestratorChannel.ANSWER
