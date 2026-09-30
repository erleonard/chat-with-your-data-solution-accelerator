"""Synthesis request model."""

from pydantic import BaseModel, Field

from backend.core.tools.synthesize import SynthesisFormat


class SynthesisRequest(BaseModel):
    """POST /api/synthesize request body."""

    document_sources: list[str] = Field(
        min_length=1,
        max_length=50,
        description=(
            "Source names (as listed by GET /api/admin/documents) to read in "
            "full and synthesize. At least one is required."
        ),
    )
    format: SynthesisFormat = Field(
        default=SynthesisFormat.PROJECT_DOCUMENTATION,
        description="Shape of the synthesized artifact.",
    )
    instructions: str | None = Field(
        default=None,
        max_length=4000,
        description=(
            "Optional focus for the synthesis (for example the audience or "
            "the sections to emphasize). Answers stay grounded in the "
            "selected documents regardless."
        ),
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Existing conversation id to append the result to. Omit or send "
            "null to start a new conversation."
        ),
    )
