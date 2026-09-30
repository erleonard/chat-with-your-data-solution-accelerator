"""Synthesis service helpers consumed by ``backend.routers.synthesize``."""

from typing import AsyncIterator

from backend.core.tools.content_safety import ContentSafetyGuard
from backend.core.tools.synthesize import SynthesisFormat
from backend.core.types import OrchestratorChannel, OrchestratorEvent
from backend.models.synthesize import SynthesisRequest

_FORMAT_LABELS: dict[SynthesisFormat, str] = {
    SynthesisFormat.PROJECT_DOCUMENTATION: "project documentation",
}


def synthesis_question(body: SynthesisRequest) -> str:
    """Return the user-turn text recorded in history for a synthesis run."""
    question = (
        f"Synthesize {_FORMAT_LABELS[body.format]} from: "
        f"{', '.join(body.document_sources)}"
    )
    if body.instructions and body.instructions.strip():
        question = f"{question}\n\nFocus: {body.instructions.strip()}"
    return question


async def screened(
    events: AsyncIterator[OrchestratorEvent],
    *,
    instructions: str | None,
    content_safety: ContentSafetyGuard | None,
) -> AsyncIterator[OrchestratorEvent]:
    """Screen ``instructions`` with the content-safety guard, then pass ``events`` through.

    A flagged focus text yields a single ``error`` event and the
    synthesis stream is never started.
    """
    if content_safety is not None and instructions and instructions.strip():
        verdict = await content_safety.screen(instructions)
        if verdict.flagged:
            yield OrchestratorEvent(
                channel=OrchestratorChannel.ERROR,
                content="Input was blocked by the content safety guard.",
                metadata={"code": "content_safety", "triggered": verdict.triggered},
            )
            return
    async for event in events:
        yield event
