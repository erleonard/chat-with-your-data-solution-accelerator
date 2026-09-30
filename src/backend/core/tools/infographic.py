"""AI-generated infographic images.

Turns an already-grounded answer (typically the ``infographic``
synthesis output) into one illustrated image. Two steps:

* **brief** -- the chat model rewrites the answer as a concise visual
  brief (layout, sections, the exact short labels and figures to
  draw). It may only reuse facts present in the answer, so the image
  stays restricted to the uploaded documents;
* **render** -- the brief is sent to the gpt-image deployment through
  ``BaseLLMProvider.generate_image``.

Citation markers cannot survive into pixels, so they are stripped
from the input; the caller keeps the cited Markdown alongside the
image for traceability.
"""

from pydantic import BaseModel, ConfigDict

from backend.core.providers.llm.base import BaseLLMProvider
from backend.core.settings import ImageSize
from backend.core.tools.citations import strip_doc_markers
from backend.core.types import ChatMessage, ChatRole, GeneratedImage

BRIEF_MAX_CHARS = 3500

BRIEF_INSTRUCTIONS = (
    "You write art-direction briefs for an image model that draws a single "
    "professional infographic poster.\n"
    "Rules:\n"
    "- Use ONLY facts, names, numbers, and dates that appear in the provided "
    "text. Never add, infer, or embellish information.\n"
    "- Choose a clear title and at most six sections (for example key "
    "figures, timeline, components, risks, next steps).\n"
    "- For every section give the exact short labels to render as text "
    "(at most eight words each) and a suggested icon or chart.\n"
    "- Describe a clean, flat, corporate style with a limited colour "
    "palette, generous whitespace, and legible sans-serif typography.\n"
    f"- Output only the brief, no preamble, under {BRIEF_MAX_CHARS} characters."
)


class InfographicImage(BaseModel):
    """A rendered infographic plus the brief that produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    image: GeneratedImage
    brief: str


class InfographicPainter:
    """Render a grounded answer as an AI-generated infographic image."""

    def __init__(
        self,
        *,
        llm: BaseLLMProvider,
        deployment: str,
        size: ImageSize = ImageSize.PORTRAIT,
    ) -> None:
        self._llm = llm
        self._deployment = deployment
        self._size = size

    async def write_brief(self, markdown: str, *, title: str | None = None) -> str:
        """Condense ``markdown`` into an image brief that adds no new facts."""
        heading = f"Infographic title: {title.strip()}\n\n" if title and title.strip() else ""
        reply = await self._llm.chat(
            [
                ChatMessage(role=ChatRole.SYSTEM, content=BRIEF_INSTRUCTIONS),
                ChatMessage(
                    role=ChatRole.USER,
                    content=f"{heading}Source text:\n\n{strip_doc_markers(markdown)}",
                ),
            ],
            temperature=0.0,
        )
        return reply.content.strip()[:BRIEF_MAX_CHARS]

    async def paint(self, markdown: str, *, title: str | None = None) -> InfographicImage:
        """Write the brief and render it through the image deployment."""
        brief = await self.write_brief(markdown, title=title)
        if not brief:
            raise ValueError("The answer produced an empty infographic brief.")
        image = await self._llm.generate_image(
            brief, deployment=self._deployment, size=self._size
        )
        return InfographicImage(image=image, brief=brief)
