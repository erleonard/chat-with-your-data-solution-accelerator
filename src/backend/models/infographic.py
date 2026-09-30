"""Request / response models for ``POST /api/infographic/image``."""

from pydantic import BaseModel, ConfigDict, Field


class InfographicImageRequest(BaseModel):
    """A grounded answer to render as an AI-generated infographic."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(
        min_length=1,
        max_length=200_000,
        description="Grounded Markdown answer (typically the infographic synthesis output).",
    )
    title: str | None = Field(
        default=None,
        max_length=300,
        description="Optional title to feature on the infographic.",
    )


class InfographicImageResponse(BaseModel):
    """A base64-encoded infographic image and the brief used to draw it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    image_base64: str
    media_type: str
    brief: str
    ai_generated: bool = True
