"""Synthesis router.

Single endpoint: ``POST /api/synthesize``. Reads the selected
documents in full and returns one grounded artifact (see
``backend.core.tools.synthesize``). Content-negotiated like
``/api/conversation``: ``text/event-stream`` streams the locked SSE
channel set, anything else returns a buffered ``ConversationResponse``.
The result is persisted as a conversation turn so it appears in the
history panel.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from backend.core.tools.synthesize import DocumentSynthesizer
from backend.dependencies import (
    ContentSafetyGuardDep,
    DatabaseClientDep,
    LLMProviderDep,
    RuntimeOverridesDep,
    SearchProviderDep,
    SettingsDep,
    UserIdDep,
)
from backend.models.conversation import ConversationResponse
from backend.models.synthesize import SynthesisRequest
from backend.services.admin import resolve_effective_config
from backend.services.conversation import (
    collect_response,
    persist_turn,
    persisting_sse_stream,
)
from backend.services.sse import SSE_MEDIA_TYPE, wants_sse
from backend.services.synthesize import screened, synthesis_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["synthesize"])

@router.post(
    "/synthesize",
    response_model=None,
    summary="Synthesize selected documents",
    description=(
        "Read every section of the selected documents and synthesize one "
        "grounded artifact (for example project documentation) with [docN] "
        "citations. Streams reasoning progress, citations, and the answer as "
        "SSE when the Accept header requests an event stream; otherwise "
        "returns a buffered JSON response."
    ),
    responses={
        200: {
            "model": ConversationResponse,
            "description": "Buffered JSON answer or an SSE stream depending on Accept.",
            "content": {"text/event-stream": {}},
        },
        503: {"description": "No search backend is configured."},
    },
)
async def synthesize(
    request: Request,
    body: SynthesisRequest,
    settings: SettingsDep,
    llm: LLMProviderDep,
    search: SearchProviderDep,
    db: DatabaseClientDep,
    user_id: UserIdDep,
    content_safety: ContentSafetyGuardDep,
    overrides: RuntimeOverridesDep,
    accept: Annotated[
        str | None,
        Header(
            description=(
                "Response negotiation: 'text/event-stream' streams SSE frames; "
                "otherwise a buffered JSON ConversationResponse is returned."
            ),
        ),
    ] = None,
) -> ConversationResponse | StreamingResponse:
    """Synthesize the selected documents and stream / buffer the result."""
    if search is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Synthesis requires a configured search backend.",
        )
    effective = resolve_effective_config(settings, overrides)
    synthesizer = DocumentSynthesizer(
        llm=llm,
        search=search,
        max_tokens=settings.openai.synthesis_max_tokens,
        batch_chars=settings.openai.synthesis_batch_chars,
        temperature=effective.openai_temperature,
    )
    events = screened(
        synthesizer.run(
            body.document_sources,
            synthesis_format=body.format,
            instructions=body.instructions,
        ),
        instructions=body.instructions,
        content_safety=content_safety,
    )
    question = synthesis_question(body)

    if wants_sse(accept):
        return StreamingResponse(
            persisting_sse_stream(
                events,
                request,
                db=db,
                user_id=user_id,
                conversation_id=body.conversation_id,
                question=question,
            ),
            media_type=SSE_MEDIA_TYPE,
        )

    response = await collect_response(events, conversation_id=body.conversation_id)
    if response.content:
        try:
            resolved_id = await persist_turn(
                db,
                user_id=user_id,
                conversation_id=body.conversation_id,
                question=question,
                answer=response.content,
                citations=response.citations,
            )
        except Exception:  # noqa: BLE001 -- answer already collected; never fail on a storage error
            logger.exception(
                "Failed to persist synthesis turn.",
                extra={
                    "operation": "persist_turn",
                    "user_id": user_id,
                    "conversation_id": body.conversation_id,
                },
            )
        else:
            response = response.model_copy(update={"conversation_id": resolved_id})
    return response
