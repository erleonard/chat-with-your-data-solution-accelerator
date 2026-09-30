"""Request model for document export."""

from pydantic import BaseModel, ConfigDict, Field

EXPORT_MAX_MARKDOWN_CHARS = 2_000_000


class DocxExportRequest(BaseModel):
    """Markdown answer to render as a Word document."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Project documentation", min_length=1, max_length=200)
    markdown: str = Field(min_length=1, max_length=EXPORT_MAX_MARKDOWN_CHARS)
