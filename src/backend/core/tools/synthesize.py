"""Whole-document synthesis over selected sources.

Chat retrieval hands the model the top-k chunks most similar to a
question, which is the wrong shape for "read these documents and
write the project documentation": the answer needs every page. This
tool reads each selected source in full through
``BaseSearch.list_chunks`` and runs a map-reduce over the text:

* **map** -- the ordered chunks are packed into batches under a
  character budget; each batch is condensed into grounded notes that
  keep the globally-unique ``[docN]`` markers of the chunks they use;
* **reduce** -- the notes are merged (in several passes when they
  exceed the budget) into one Markdown artifact whose shape is chosen
  by :class:`SynthesisFormat`.

Every completion is grounded by the shared ``CWYD_GUARDRAIL`` and every
source is rendered by the shared ``format_sources_block``; the final
answer is shaped by ``renumber_referenced`` so the output matches the
chat citation contract (Hard Rule #20). Progress is narrated on the
``reasoning`` channel so a long run shows activity in the thinking
panel.
"""

import asyncio
import logging
from enum import StrEnum
from typing import AsyncIterator, Sequence

from pydantic import BaseModel, ConfigDict, Field

from backend.core.agents.definitions import compose_cwyd_instructions
from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.providers.search.base import BaseSearch
from backend.core.tools.citations import (
    build_citations,
    format_sources_block,
    renumber_referenced,
)
from backend.core.types import (
    ChatMessage,
    ChatRole,
    Citation,
    OrchestratorChannel,
    OrchestratorEvent,
    SearchResult,
)

logger = logging.getLogger(__name__)

NO_CONTENT_MESSAGE = "The selected documents have no indexed content to synthesize."
MAP_CONCURRENCY = 4
MAX_CONDENSE_PASSES = 3


class SynthesisFormat(StrEnum):
    """Shape of the synthesized artifact."""

    PROJECT_DOCUMENTATION = "project_documentation"


class SynthesisBatch(BaseModel):
    """A run of consecutive chunks condensed by one map call.

    ``start`` is the 1-based global ``[docN]`` index of the first chunk
    so markers stay unique across batches.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: int = Field(ge=1)
    chunks: list[SearchResult]


_MAP_BODY = """You are a meticulous analyst reading one excerpt of a larger document set.
Extract every fact from the excerpt that matters for understanding the project it describes: goals, scope, stakeholders, requirements, architecture and components, data, integrations, decisions, constraints, risks, dependencies, milestones, dates, costs, and open questions.
Write concise bullet-point notes grouped under short headings. Keep the exact [docN] marker of the source line at the end of every bullet. Do not add information that is not in the excerpt, and do not summarize away specific names, numbers, or dates."""

_REDUCE_BODIES: dict[SynthesisFormat, str] = {
    SynthesisFormat.PROJECT_DOCUMENTATION: """You are a technical writer producing project documentation from analyst notes that were extracted from the user's documents.
Write one well-structured Markdown document using these sections, in order, omitting any section the notes do not support:
# <Project name>
## Executive summary
## Background and objectives
## Scope (in scope / out of scope)
## Stakeholders and roles
## Requirements
## Solution overview and architecture
## Data and integrations
## Timeline and milestones
## Decisions
## Risks, issues, and dependencies
## Open questions
Use tables where they help (for example milestones or risks). Merge duplicate facts, resolve ordering, and keep every [docN] marker from the notes at the end of the sentence it supports. Never invent facts, names, or dates that are not in the notes.""",
}

_CONDENSE_BODY = """You merge overlapping analyst notes into one deduplicated set of bullet-point notes grouped under short headings.
Keep every distinct fact and the exact [docN] markers attached to it. Do not add information that is not in the notes."""


def build_batches(
    chunks: Sequence[SearchResult], *, max_chars: int
) -> list[SynthesisBatch]:
    """Pack ordered ``chunks`` into consecutive batches under ``max_chars``.

    A chunk longer than the budget gets a batch of its own rather than
    being split, so no source text is dropped.
    """
    batches: list[SynthesisBatch] = []
    current: list[SearchResult] = []
    current_start = 1
    size = 0
    for index, chunk in enumerate(chunks, start=1):
        length = len(chunk.content)
        if current and size + length > max_chars:
            batches.append(SynthesisBatch(start=current_start, chunks=current))
            current, size, current_start = [], 0, index
        current.append(chunk)
        size += length
    if current:
        batches.append(SynthesisBatch(start=current_start, chunks=current))
    return batches


def group_notes(notes: Sequence[str], *, max_chars: int) -> list[list[str]]:
    """Group consecutive ``notes`` so each group stays under ``max_chars``."""
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0
    for note in notes:
        if current and size + len(note) > max_chars:
            groups.append(current)
            current, size = [], 0
        current.append(note)
        size += len(note)
    if current:
        groups.append(current)
    return groups


def _progress(text: str) -> OrchestratorEvent:
    return OrchestratorEvent(channel=OrchestratorChannel.REASONING, content=f"{text}\n")


class DocumentSynthesizer:
    """Map-reduce synthesis of whole documents into one grounded artifact."""

    def __init__(
        self,
        *,
        llm: BaseLLMProvider,
        search: BaseSearch,
        max_tokens: int,
        batch_chars: int,
        temperature: float = 0.0,
    ) -> None:
        self._llm = llm
        self._search = search
        self._max_tokens = max_tokens
        self._batch_chars = batch_chars
        self._temperature = temperature

    async def _complete(self, body: str, user_text: str) -> str:
        reply = await self._llm.chat(
            [
                ChatMessage(role=ChatRole.SYSTEM, content=compose_cwyd_instructions(body)),
                ChatMessage(role=ChatRole.USER, content=user_text),
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return reply.content.strip()

    async def _map_batch(self, batch: SynthesisBatch, focus: str) -> str:
        sources = format_sources_block(batch.chunks, start=batch.start)
        return await self._complete(
            _MAP_BODY,
            f"{focus}Retrieved documents:\n{sources}\n\nWrite the notes for this excerpt.",
        )

    async def _condense(self, notes: Sequence[str], focus: str) -> str:
        joined = "\n\n".join(notes)
        return await self._complete(
            _CONDENSE_BODY,
            f"{focus}Retrieved documents (analyst notes):\n{joined}\n\nWrite the merged notes.",
        )

    async def run(
        self,
        sources: Sequence[str],
        *,
        synthesis_format: SynthesisFormat = SynthesisFormat.PROJECT_DOCUMENTATION,
        instructions: str | None = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Synthesize ``sources`` and yield progress, citations, then the answer."""
        focus = f"User focus: {instructions.strip()}\n\n" if instructions and instructions.strip() else ""

        chunks: list[SearchResult] = []
        for source in sources:
            yield _progress(f"Reading {source}\u2026")
            document_chunks = await self._search.list_chunks(source)
            chunks.extend(document_chunks)
            yield _progress(f"Read {len(document_chunks)} sections from {source}.")

        if not chunks:
            yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content=NO_CONTENT_MESSAGE)
            return

        citations: list[Citation] = build_citations(chunks)
        batches = build_batches(chunks, max_chars=self._batch_chars)
        yield _progress(f"Analyzing {len(chunks)} sections in {len(batches)} passes\u2026")

        semaphore = asyncio.Semaphore(MAP_CONCURRENCY)

        async def bounded_map(position: int, batch: SynthesisBatch) -> tuple[int, str]:
            async with semaphore:
                return position, await self._map_batch(batch, focus)

        notes: list[str] = [""] * len(batches)
        tasks = [
            asyncio.create_task(bounded_map(position, batch))
            for position, batch in enumerate(batches)
        ]
        try:
            for done, finished in enumerate(asyncio.as_completed(tasks), start=1):
                position, note = await finished
                notes[position] = note
                yield _progress(f"Analyzed pass {done} of {len(batches)}.")
        finally:
            for task in tasks:
                task.cancel()

        notes = [note for note in notes if note]
        passes = 0
        while (
            passes < MAX_CONDENSE_PASSES
            and len(notes) > 1
            and sum(len(note) for note in notes) > self._batch_chars
        ):
            passes += 1
            groups = group_notes(notes, max_chars=self._batch_chars)
            if len(groups) == len(notes):
                groups = [list(notes[i : i + 2]) for i in range(0, len(notes), 2)]
            yield _progress(f"Consolidating {len(notes)} note sets\u2026")
            notes = [await self._condense(group, focus) for group in groups]

        yield _progress("Writing the final document\u2026")
        joined = "\n\n".join(notes)
        answer = await self._complete(
            _REDUCE_BODIES[synthesis_format],
            f"{focus}Retrieved documents (analyst notes):\n{joined}\n\nWrite the document.",
        )

        answer, referenced = renumber_referenced(answer, citations)
        for citation in referenced:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.CITATION,
                metadata=citation.model_dump(),
            )
        yield OrchestratorEvent(channel=OrchestratorChannel.ANSWER, content=answer)
