import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MarkdownContent } from "@/pages/chat/components/MarkdownContent";

const { initializeMock, renderMock } = vi.hoisted(() => ({
  initializeMock: vi.fn(),
  renderMock: vi.fn(),
}));

vi.mock("mermaid", () => ({
  default: { initialize: initializeMock, render: renderMock },
}));

const DIAGRAM = "```mermaid\nflowchart TD\n  A[Plan] ^1^ --> B[Build] [doc2]\n```";

describe("MermaidDiagram via MarkdownContent", () => {
  beforeEach(() => {
    initializeMock.mockReset();
    renderMock.mockReset();
  });

  it("renders mermaid fences as sanitized SVG without a <pre> wrapper", async () => {
    renderMock.mockResolvedValue({ svg: '<svg data-testid="svg-out"></svg>' });
    const { container } = render(
      <MarkdownContent content={`Intro\n\n${DIAGRAM}`} enableSupersub />,
    );

    await screen.findByTestId("mermaid-diagram");
    expect(screen.getByTestId("svg-out")).toBeInTheDocument();
    expect(container.querySelector("pre")).toBeNull();
    expect(initializeMock).toHaveBeenCalledWith(
      expect.objectContaining({ startOnLoad: false, securityLevel: "strict" }),
    );
    const [id, code] = renderMock.mock.calls[0] as [string, string];
    expect(id).toMatch(/^mermaid-[A-Za-z0-9_-]+$/);
    expect(code).toBe("flowchart TD\n  A[Plan] --> B[Build]");
  });

  it("falls back to the diagram source when rendering fails", async () => {
    renderMock.mockRejectedValue(new Error("Parse error"));
    render(<MarkdownContent content={DIAGRAM} />);

    const fallback = await screen.findByTestId("mermaid-failed");
    expect(fallback.textContent).toBe("flowchart TD\n  A[Plan] --> B[Build]");
  });

  it("leaves other code blocks untouched", async () => {
    const { container } = render(
      <MarkdownContent content={"```js\nconst x = 1;\n```"} />,
    );
    await waitFor(() => {
      expect(container.querySelector("pre > code.language-js")).not.toBeNull();
    });
    expect(renderMock).not.toHaveBeenCalled();
  });
});
