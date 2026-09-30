import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildExportDocument,
  downloadDocx,
  downloadMarkdown,
  exportFilename,
} from "@/api/exportDocument";
import type { Citation } from "@/models/chat";

function citation(id: string, title: string, url = ""): Citation {
  return { id, title, url, snippet: "", score: null, metadata: {} };
}

describe("buildExportDocument", () => {
  it("renumbers markers in first-use order and lists referenced sources", () => {
    const doc = buildExportDocument(
      "## Summary\n\nB [doc2] then A [doc1] and B again [doc2] [doc9].",
      [citation("a", "a.pdf"), citation("b", "b.docx", "https://x/b.docx")],
    );
    expect(doc.title).toBe("Summary");
    expect(doc.markdown).toBe(
      "## Summary\n\nB [1] then A [2] and B again [1] [doc9].\n\n" +
        "## Sources\n\n1. b.docx — https://x/b.docx\n2. a.pdf\n",
    );
  });

  it("uses a default title and omits Sources when nothing is cited", () => {
    expect(buildExportDocument("plain answer  ", undefined)).toEqual({
      title: "Chat answer",
      markdown: "plain answer\n",
    });
  });
});

describe("exportFilename", () => {
  it("sanitizes titles", () => {
    expect(exportFilename("Q3 plan: v2/final", "docx")).toBe("Q3-plan-v2-final.docx");
    expect(exportFilename("///", "md")).toBe("document.md");
  });
});

describe("downloads", () => {
  const fetchMock = vi.fn();
  const createObjectURL = vi.fn(() => "blob:x");
  const revokeObjectURL = vi.fn();
  let clicked: string[] = [];

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    clicked = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      function (this: HTMLAnchorElement) {
        clicked.push(this.download);
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    fetchMock.mockReset();
  });

  it("saves Markdown client-side", () => {
    downloadMarkdown({ title: "My Doc", markdown: "# x" });
    expect(clicked).toEqual(["My-Doc.md"]);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:x");
  });

  it("posts to the docx export endpoint and saves the blob", async () => {
    fetchMock.mockResolvedValueOnce(new Response(new Blob(["docx"]), { status: 200 }));
    await downloadDocx({ title: "My Doc", markdown: "# x" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith("/api/export/docx")).toBe(true);
    expect(JSON.parse(init.body as string)).toEqual({ title: "My Doc", markdown: "# x" });
    expect(clicked).toEqual(["My-Doc.docx"]);
  });

  it("throws on a non-2xx response", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 422 }));
    await expect(downloadDocx({ title: "t", markdown: "x" })).rejects.toThrow(
      "status 422",
    );
    expect(clicked).toEqual([]);
  });
});
