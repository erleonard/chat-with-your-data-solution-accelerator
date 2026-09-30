import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatProvider, useChat } from "@/pages/chat/ChatContext";
import { DocumentScopePicker } from "@/pages/chat/components/DocumentScopePicker";
import { listDocuments } from "@/api/admin";

vi.mock("@/api/admin", () => ({
  listDocuments: vi.fn(),
}));

const listDocumentsMock = vi.mocked(listDocuments);

function ScopeProbe() {
  const { state } = useChat();
  return (
    <div data-testid="scope-probe">{JSON.stringify(state.documentSources)}</div>
  );
}

function renderPicker() {
  return render(
    <ChatProvider>
      <DocumentScopePicker />
      <ScopeProbe />
    </ChatProvider>,
  );
}

beforeEach(() => {
  listDocumentsMock.mockReset();
});

describe("DocumentScopePicker", () => {
  it("defaults to all documents and records selections in chat state", async () => {
    listDocumentsMock.mockResolvedValue({
      documents: [
        { source: "b.docx", chunk_count: 3, last_modified: null },
        { source: "a.pdf", chunk_count: 120, last_modified: null },
      ],
      total: 2,
    });
    renderPicker();

    const picker = await screen.findByTestId("document-scope-picker");
    expect(picker).toHaveTextContent("All documents");

    fireEvent.click(picker);
    fireEvent.click(await screen.findByText("a.pdf"));

    await waitFor(() => {
      expect(screen.getByTestId("scope-probe")).toHaveTextContent('["a.pdf"]');
    });
  });

  it("renders nothing when the document listing fails", async () => {
    listDocumentsMock.mockRejectedValue(new Error("403"));
    renderPicker();
    await waitFor(() => {
      expect(listDocumentsMock).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("document-scope-picker")).toBeNull();
  });
});
