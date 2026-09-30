import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { InfographicImageAction } from "@/pages/chat/components/InfographicImageAction";

const generateMock = vi.fn();
vi.mock("@/api/infographicImage", async () => {
  const actual = await vi.importActual<typeof import("@/api/infographicImage")>(
    "@/api/infographicImage",
  );
  return {
    ...actual,
    generateInfographicImage: (...args: unknown[]) => generateMock(...args) as Promise<unknown>,
  };
});

beforeEach(() => {
  generateMock.mockReset();
});

describe("InfographicImageAction", () => {
  it("renders the generated image labelled as AI-generated", async () => {
    generateMock.mockResolvedValueOnce({
      imageBase64: "aW1n",
      mediaType: "image/png",
      brief: "Poster",
    });
    const onError = vi.fn();
    render(
      <InfographicImageAction messageId="7" markdown="Ships [doc1]." title="Plan" onError={onError} />,
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("answer-image-7"));
      await Promise.resolve();
    });
    expect(generateMock).toHaveBeenCalledWith("Ships [doc1].", "Plan");
    const figure = await screen.findByTestId("answer-image-result-7");
    const img = figure.querySelector("img");
    expect(img?.getAttribute("src")).toBe("data:image/png;base64,aW1n");
    expect(img?.getAttribute("alt")).toBe("AI-generated infographic: Plan");
    expect(figure.textContent).toContain("AI-generated image");
    expect(figure.querySelector("a")?.getAttribute("download")).toBe("Plan.png");
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports failures through onError and shows no image", async () => {
    const failure = new Error("not configured");
    generateMock.mockRejectedValueOnce(failure);
    const onError = vi.fn();
    render(<InfographicImageAction messageId="8" markdown="x" title="t" onError={onError} />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("answer-image-8"));
      await Promise.resolve();
    });
    expect(onError).toHaveBeenCalledWith(failure);
    expect(screen.queryByTestId("answer-image-result-8")).toBeNull();
    expect(screen.getByTestId("answer-image-8").hasAttribute("disabled")).toBe(false);
  });
});
