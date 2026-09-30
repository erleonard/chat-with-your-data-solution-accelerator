/**
 * Renders an assistant-supplied markdown string as HTML. Both the answer
 * body and the reasoning panel feed their text through here so the
 * model's markdown -- bold, lists, headings, fenced code, and the
 * GitHub-flavoured extensions (tables, strikethrough, task lists,
 * autolinks) -- displays as formatted HTML instead of literal source.
 *
 * Rendering goes through `react-markdown` with `remark-gfm` and no
 * raw-HTML rehype pass (`rehype-raw` is deliberately omitted), so any
 * literal HTML embedded in the model output is escaped rather than
 * mounted as live nodes. Anchor links are forced to open in a new tab
 * with `rel="noreferrer"` so a cited destination cannot reach back into
 * the app through `window.opener`.
 *
 * When `enableSupersub` is set, `remark-supersub` is added to the remark
 * pipeline so `^text^` renders as a `<sup>` (and `~text~` as a `<sub>`).
 * Both the answer body and the reasoning panel enable it: the answer
 * body renders the `^K^` citation tokens emitted by `parseAnswer`, and
 * the reasoning panel renders the `^N^` tokens emitted by
 * `superscriptReasoningCitations`, so citation markers show as visual
 * superscripts in both surfaces. A stray `^..^` pair in chain-of-thought
 * therefore renders as a `<sup>` (accepted, cosmetic).
 *
 * Fenced ```mermaid blocks render as diagrams through `MermaidDiagram`
 * (the surrounding `<pre>` is dropped for them); every other code block
 * renders unchanged.
 */
import { isValidElement } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from "remark-supersub";
import { MermaidDiagram } from "./MermaidDiagram";

const REMARK_PLUGINS = [remarkGfm];
const REMARK_PLUGINS_WITH_SUPERSUB = [remarkGfm, supersub];

const MERMAID_LANGUAGE = "language-mermaid";

function isMermaidCode(className: string | undefined): boolean {
  return className?.split(" ").includes(MERMAID_LANGUAGE) ?? false;
}

const COMPONENTS: Components = {
  a({ href, children }) {
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  },
  pre({ children }) {
    if (
      isValidElement<{ className?: string }>(children) &&
      isMermaidCode(children.props.className)
    ) {
      return children;
    }
    return <pre>{children}</pre>;
  },
  code({ className, children }) {
    if (isMermaidCode(className)) {
      return (
        <MermaidDiagram
          source={typeof children === "string" ? children : ""}
        />
      );
    }
    return <code className={className}>{children}</code>;
  },
};

export function MarkdownContent({
  content,
  className,
  enableSupersub = false,
}: {
  content: string;
  className?: string | undefined;
  enableSupersub?: boolean | undefined;
}) {
  const remarkPlugins = enableSupersub
    ? REMARK_PLUGINS_WITH_SUPERSUB
    : REMARK_PLUGINS;
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={remarkPlugins} components={COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
