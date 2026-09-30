/**
 * Renders a Mermaid diagram (the ```mermaid fences emitted by the
 * infographic synthesis format) as inline SVG.
 *
 * `mermaid` is loaded with a dynamic `import()` so the library ships as
 * a separate chunk fetched only when a diagram is on screen. It runs
 * with `securityLevel: "strict"` (labels are sanitized, click handlers
 * and HTML labels are disabled). Citation tokens that leaked into the
 * diagram source (`^N^` superscripts from `parseAnswer`, raw `[docN]`)
 * are stripped before parsing because they are not valid Mermaid
 * syntax. When parsing or rendering fails, the source is shown as a
 * plain code block so no content is lost.
 */
import { useEffect, useId, useState } from "react";

const CITATION_TOKENS = /\s*(?:\^[\d,\s]+\^|\[doc\d+\])/g;

function sanitizeMermaidSource(source: string): string {
  return source.replace(CITATION_TOKENS, "").trim();
}

type RenderState =
  | { status: "pending" }
  | { status: "ready"; svg: string }
  | { status: "failed" };

export function MermaidDiagram({ source }: { source: string }) {
  const reactId = useId();
  const [state, setState] = useState<RenderState>({ status: "pending" });
  const code = sanitizeMermaidSource(source);

  useEffect(() => {
    let cancelled = false;
    const diagramId = `mermaid-${reactId.replace(/[^A-Za-z0-9_-]/g, "")}`;
    setState({ status: "pending" });
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "neutral",
        });
        const { svg } = await mermaid.render(diagramId, code);
        if (!cancelled) setState({ status: "ready", svg });
      })
      .catch(() => {
        document.getElementById(`d${diagramId}`)?.remove();
        if (!cancelled) setState({ status: "failed" });
      });
    return () => {
      cancelled = true;
    };
  }, [code, reactId]);

  if (state.status === "ready") {
    return (
      <figure
        data-testid="mermaid-diagram"
        role="img"
        aria-label="Diagram"
        style={{ margin: "8px 0", overflowX: "auto" }}
        dangerouslySetInnerHTML={{ __html: state.svg }}
      />
    );
  }
  return (
    <pre data-testid={`mermaid-${state.status}`}>
      <code className="language-mermaid">{code}</code>
    </pre>
  );
}
