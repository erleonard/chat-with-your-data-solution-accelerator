/**
 * Export of finished assistant answers as Markdown or Word files.
 *
 * `buildExportDocument` turns an answer's raw content plus its citation
 * list into a standalone Markdown document: `[docN]` markers become
 * plain `[N]` references numbered in first-use order, and a trailing
 * "Sources" section lists each referenced document. The `.md` download
 * happens client-side; the `.docx` download posts that Markdown to
 * `POST /api/export/docx`.
 */
import { userIdHeaders } from "@/api/auth";
import { getBackendUrl } from "@/api/runtimeConfig";
import type { Citation } from "@/models/chat";

export const EXPORT_DOCX_PATH = "/api/export/docx";
const DEFAULT_TITLE = "Chat answer";
const DOC_MARKER_PATTERN = /\[doc(\d+)\]/g;
const HEADING_PATTERN = /^#{1,2}\s+(.+?)\s*#*\s*$/m;
const FILENAME_UNSAFE = /[^A-Za-z0-9._-]+/g;

export interface ExportDocument {
  title: string;
  markdown: string;
}

function sourceLine(citation: Citation, index: number): string {
  const title = citation.title.length > 0 ? citation.title : citation.id;
  const url = citation.url.length > 0 ? ` — ${citation.url}` : "";
  return `${index + 1}. ${title}${url}`;
}

export function buildExportDocument(
  content: string,
  citations: Citation[] | undefined,
): ExportDocument {
  const all = citations ?? [];
  const referenced: Citation[] = [];
  const numberById = new Map<string, number>();
  const body = content.replace(
    DOC_MARKER_PATTERN,
    (raw: string, oneBasedStr: string): string => {
      const citation = all[Number.parseInt(oneBasedStr, 10) - 1];
      if (citation === undefined) return raw;
      let n = numberById.get(citation.id);
      if (n === undefined) {
        n = referenced.length + 1;
        numberById.set(citation.id, n);
        referenced.push(citation);
      }
      return `[${n}]`;
    },
  );
  const heading = HEADING_PATTERN.exec(content);
  const title = heading?.[1]?.trim() ?? DEFAULT_TITLE;
  const sources =
    referenced.length > 0
      ? `\n\n## Sources\n\n${referenced.map(sourceLine).join("\n")}\n`
      : "\n";
  return { title, markdown: `${body.trimEnd()}${sources}` };
}

export function exportFilename(title: string, extension: string): string {
  const stem = title.replace(FILENAME_UNSAFE, "-").replace(/^[-.]+|[-.]+$/g, "");
  return `${(stem.length > 0 ? stem : "document").slice(0, 100)}.${extension}`;
}

function saveBlob(blob: Blob, filename: string): void {
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(href);
}

export function downloadMarkdown(doc: ExportDocument): void {
  saveBlob(
    new Blob([doc.markdown], { type: "text/markdown;charset=utf-8" }),
    exportFilename(doc.title, "md"),
  );
}

/**
 * @throws Error when the export endpoint returns a non-2xx status.
 */
export async function downloadDocx(doc: ExportDocument): Promise<void> {
  const response = await fetch(`${getBackendUrl()}${EXPORT_DOCX_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...userIdHeaders() },
    body: JSON.stringify({ title: doc.title, markdown: doc.markdown }),
  });
  if (!response.ok) {
    throw new Error(`downloadDocx: request failed with status ${response.status}`);
  }
  saveBlob(await response.blob(), exportFilename(doc.title, "docx"));
}
