/**
 * Client for `POST /api/infographic/image`, which renders a grounded
 * answer as an AI-generated infographic through the optional gpt-image
 * deployment.
 */
import { userIdHeaders } from "@/api/auth";
import { getBackendUrl } from "@/api/runtimeConfig";

export const INFOGRAPHIC_IMAGE_PATH = "/api/infographic/image";

export interface InfographicImage {
  imageBase64: string;
  mediaType: string;
  brief: string;
}

interface InfographicImageWire {
  image_base64: string;
  media_type: string;
  brief: string;
}

/**
 * @throws Error when the endpoint returns a non-2xx status; a 503 means
 *   no image deployment is configured.
 */
export async function generateInfographicImage(
  markdown: string,
  title: string,
): Promise<InfographicImage> {
  const response = await fetch(`${getBackendUrl()}${INFOGRAPHIC_IMAGE_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...userIdHeaders() },
    body: JSON.stringify({ markdown, title }),
  });
  if (response.status === 503) {
    throw new Error("Image generation is not configured for this deployment.");
  }
  if (!response.ok) {
    throw new Error(
      `generateInfographicImage: request failed with status ${response.status}`,
    );
  }
  const body = (await response.json()) as InfographicImageWire;
  return {
    imageBase64: body.image_base64,
    mediaType: body.media_type,
    brief: body.brief,
  };
}

export function imageDataUrl(image: InfographicImage): string {
  return `data:${image.mediaType};base64,${image.imageBase64}`;
}
