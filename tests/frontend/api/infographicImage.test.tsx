import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  generateInfographicImage,
  imageDataUrl,
  INFOGRAPHIC_IMAGE_PATH,
} from "@/api/infographicImage";

describe("generateInfographicImage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("posts the answer and maps the wire response", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          image_base64: "aW1n",
          media_type: "image/png",
          brief: "Poster",
          ai_generated: true,
        }),
        { status: 200 },
      ),
    );
    const image = await generateInfographicImage("Ships in May [doc1].", "Plan");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith(INFOGRAPHIC_IMAGE_PATH)).toBe(true);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      markdown: "Ships in May [doc1].",
      title: "Plan",
    });
    expect(image).toEqual({ imageBase64: "aW1n", mediaType: "image/png", brief: "Poster" });
    expect(imageDataUrl(image)).toBe("data:image/png;base64,aW1n");
  });

  it("explains a 503 as an unconfigured deployment", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 503 }));
    await expect(generateInfographicImage("x", "t")).rejects.toThrow(/not configured/);
  });

  it("throws on other non-2xx statuses", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 502 }));
    await expect(generateInfographicImage("x", "t")).rejects.toThrow(/502/);
  });
});
