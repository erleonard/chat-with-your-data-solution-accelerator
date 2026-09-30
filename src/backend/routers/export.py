"""Export router.

Single endpoint: ``POST /api/export/docx``. Renders a Markdown answer
(for example synthesized project documentation) as a Word document.
Stateless: nothing is read from or written to storage.
"""

from fastapi import APIRouter
from fastapi.responses import Response

from backend.models.export import DocxExportRequest
from backend.services.docx_export import (
    DOCX_MEDIA_TYPE,
    export_filename,
    markdown_to_docx,
)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post(
    "/docx",
    response_class=Response,
    summary="Export Markdown as a Word document",
    description="Render a Markdown answer as a downloadable .docx file.",
    responses={200: {"content": {DOCX_MEDIA_TYPE: {}}}},
)
async def export_docx(body: DocxExportRequest) -> Response:
    payload = markdown_to_docx(body.markdown, title=body.title)
    filename = export_filename(body.title, "docx")
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
