"""Infographic image router.

Single endpoint: ``POST /api/infographic/image``. Renders a grounded
answer as an AI-generated infographic through the optional gpt-image
deployment (``AZURE_OPENAI_IMAGE_DEPLOYMENT``). Stateless.
"""

from fastapi import APIRouter, HTTPException, status

from backend.core.tools.infographic import InfographicPainter
from backend.dependencies import LLMProviderDep, SettingsDep
from backend.models.infographic import InfographicImageRequest, InfographicImageResponse

router = APIRouter(prefix="/api/infographic", tags=["infographic"])


@router.post(
    "/image",
    response_model=InfographicImageResponse,
    summary="Render an AI-generated infographic image",
    description=(
        "Condense a grounded answer into a visual brief that reuses only its "
        "facts, then draw it with the configured gpt-image deployment. The "
        "result is AI-generated and should be checked against the cited answer."
    ),
    responses={503: {"description": "No image deployment is configured."}},
)
async def infographic_image(
    body: InfographicImageRequest,
    settings: SettingsDep,
    llm: LLMProviderDep,
) -> InfographicImageResponse:
    deployment = settings.openai.image_deployment
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image generation is not configured (AZURE_OPENAI_IMAGE_DEPLOYMENT).",
        )
    painter = InfographicPainter(
        llm=llm, deployment=deployment, size=settings.openai.image_size
    )
    result = await painter.paint(body.markdown, title=body.title)
    return InfographicImageResponse(
        image_base64=result.image.b64_data,
        media_type=result.image.media_type,
        brief=result.brief,
    )
