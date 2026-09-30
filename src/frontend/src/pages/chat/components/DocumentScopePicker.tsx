/**
 * Multi-select picker that scopes chat retrieval to chosen indexed
 * documents.
 *
 * Loads the indexed source list from `listDocuments()` once on mount and
 * writes the selection to `ChatContext.documentSources`, which
 * `MessageInput` forwards to `streamChat` as `document_sources`. An empty
 * selection means "all documents". When the listing fails (search not
 * configured, RBAC, backend down) the picker renders nothing so chat
 * keeps working unscoped.
 */
import { useEffect, useState } from "react";
import { Dropdown, Option } from "@fluentui/react-components";
import { listDocuments } from "@/api/admin";
import { useChat } from "@/pages/chat/ChatContext";

const ALL_DOCUMENTS_LABEL = "All documents";

export function DocumentScopePicker() {
  const { state, dispatch } = useChat();
  const [sources, setSources] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDocuments()
      .then((body) => {
        if (!cancelled) {
          setSources(body.documents.map((d) => d.source).sort());
        }
      })
      .catch(() => {
        if (!cancelled) setSources(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (sources === null || sources.length === 0) return null;

  const selected = state.documentSources.filter((s) => sources.includes(s));
  const summary =
    selected.length === 0
      ? ALL_DOCUMENTS_LABEL
      : selected.length === 1
        ? (selected[0] ?? ALL_DOCUMENTS_LABEL)
        : `${String(selected.length)} documents`;

  return (
    <Dropdown
      multiselect
      size="small"
      aria-label="Limit answers to documents"
      title="Limit answers to the selected documents"
      data-testid="document-scope-picker"
      placeholder={ALL_DOCUMENTS_LABEL}
      value={summary}
      selectedOptions={selected}
      onOptionSelect={(_event, data) => {
        dispatch({
          type: "set_document_sources",
          documentSources: [...data.selectedOptions],
        });
      }}
    >
      {sources.map((source) => (
        <Option key={source} value={source}>
          {source}
        </Option>
      ))}
    </Dropdown>
  );
}
