import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { CitationItem } from "../../types/chat";

// A single $ stays plain text: answers are full of amounts such as "$1,234 and $5,678", which must never be read as a formula.
const REMARK_PLUGINS = [remarkGfm, [remarkMath, { singleDollarTextMath: false }]] as React.ComponentProps<typeof ReactMarkdown>["remarkPlugins"];
const REHYPE_PLUGINS = [[rehypeKatex, { strict: "ignore" }]] as React.ComponentProps<typeof ReactMarkdown>["rehypePlugins"];

// A table cell that holds only a figure and its citations: "177,866 [5]", "+30.9%", "(1,204) [2][3]"
const NUMERIC_CELL = /^[+\-−–$€£(]*\d[\d.,\s]*[%)xX]?(\s*\[\d+\])*$/;

// A table header: title, an optional unit in brackets, then citations: "Prior fiscal year (USD million) [2][5]"
const HEADER_TEXT = /^(.*?)\s*(\([^)]*\))?\s*((?:\[\d+\]\s*)*)$/;

const LOOKS_LIKE_MATH =/\\[a-zA-Z]|[=^]/;
const inlineMath = (body: string) => `$$${body.trim()}$$`;
const blockMath = (body: string) => `\n\n$$\n${body.trim()}\n$$\n\n`;

/** Bring the other ways of writing a formula to $$...$$; `\[1\]` and plain amounts have no LaTeX command or operator and are left alone. */
const normalizeMath = (text: string): string =>
  text
    .replace(/\\\[([\s\S]+?)\\\]/g, (all, body: string) => (LOOKS_LIKE_MATH.test(body) ? blockMath(body) : all))
    .replace(/\\\(([\s\S]+?)\\\)/g, (all, body: string) => (LOOKS_LIKE_MATH.test(body) ? inlineMath(body) : all))
    .replace(/(?<![$\w])\$(?!\$)([^$\n]*\\[a-zA-Z][^$\n]*)\$(?!\$)/g, (_all, body: string) => inlineMath(body));

interface MarkdownRendererProps {
  content: string;
  citations?: CitationItem[];
  onSelectCitation?: (citation: CitationItem) => void;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  citations = [],
  onSelectCitation,
}) => {
  // Helper to render text with clickable citation badges [n]
  const renderTextWithCitations = (text: string) => {
    if (!text || typeof text !== "string") return text;

    const parts: React.ReactNode[] = [];
    const citeRegex = /\[(\d+)\]/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = citeRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }

      const citeNum = parseInt(match[1], 10);
      const targetCitation = citations[citeNum - 1];

      parts.push(
        <button
          key={`cite-${match.index}-${citeNum}`}
          type="button"
          className="inline-citation-pill"
          title={
            targetCitation
              ? `View source at Page ${targetCitation.page}`
              : `Source citation [${citeNum}]`
          }
          onClick={(e) => {
            e.stopPropagation();
            if (targetCitation && onSelectCitation) {
              onSelectCitation(targetCitation);
            }
          }}
        >
          {citeNum}
        </button>
      );

      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  // Process children of inline elements to replace [n] text nodes with citation pills
  const processChildren = (children: React.ReactNode): React.ReactNode => {
    return React.Children.map(children, (child) => {
      if (typeof child === "string") {
        return renderTextWithCitations(child);
      }
      return child;
    });
  };

  // A header "Prior fiscal year (USD million) [2][5]" is shown as the title with its citations, and the unit on a small line below,
  // so a long header does not break into four lines of capitals with the citation badges stacked
  const renderHeader = (children: React.ReactNode): React.ReactNode => {
    const parts = React.Children.toArray(children);
    if (!parts.every((p) => typeof p === "string")) return processChildren(children);
    const m = HEADER_TEXT.exec((parts as string[]).join("").trim());
    if (!m || !m[1]) return processChildren(children);
    return (
      <>
        <span className="th-title">{m[1]}</span>
        {m[3] && processChildren(m[3].trim())}
        {m[2] && <span className="th-unit">{m[2]}</span>}
      </>
    );
  };

  // Helper to extract plain text string from React children for content classification
  const getPlainText = (node: React.ReactNode): string => {
    if (!node) return "";
    if (typeof node === "string" || typeof node === "number") return String(node);
    if (Array.isArray(node)) return node.map(getPlainText).join("");
    if (React.isValidElement(node) && (node.props as { children?: React.ReactNode })?.children) {
      return getPlainText((node.props as { children?: React.ReactNode }).children);
    }
    return "";
  };

  // Preprocess: ensure Markdown tables have blank lines before and after so remark-gfm parses them reliably
  const normalizeMarkdown = (raw: string): string => {
    if (!raw) return "";
    let normalized = normalizeMath(raw).replace(/([^\n|])\n(\|[^\n]+\|)/g, "$1\n\n$2");
    normalized = normalized.replace(/(\|[^\n]+\|)\n([^\n|])/g, "$1\n\n$2");
    return normalized;
  };

  return (
    <div className="markdown-prose">
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={REHYPE_PLUGINS}
        // An answer is built from uploaded files: text hidden in a PDF must never make the browser load an outside image or offer an outside link
        disallowedElements={["img"]}
        components={{
          a: ({ children }) => <>{children}</>,
          table: ({ children }) => (
            <div className="table-responsive-container">
              <table className="financial-markdown-table">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="financial-thead">{children}</thead>,
          tbody: ({ children }) => <tbody className="financial-tbody">{children}</tbody>,
          tr: ({ children }) => <tr className="financial-tr">{children}</tr>,
          th: ({ children, style }) => (
            <th className="financial-th" style={style}>
              {renderHeader(children)}
            </th>
          ),
          td: ({ children, style }) => {
            const plainText = getPlainText(children).trim();
            const isDashOrNA =
              plainText === "—" ||
              plainText === "-" ||
              plainText === "–" ||
              plainText.toLowerCase() === "n/a";
            const isDeltaNegative =
              plainText.startsWith("-") ||
              plainText.startsWith("−") ||
              plainText.toLowerCase().includes("decrease") ||
              plainText.toLowerCase().includes("decline") ||
              plainText.toLowerCase().includes("giảm");
            const isDeltaPositive =
              plainText.startsWith("+") ||
              (plainText.includes("%") &&
                !plainText.startsWith("-") &&
                !plainText.startsWith("−") &&
                !plainText.toLowerCase().includes("decrease") &&
                !plainText.toLowerCase().includes("decline") &&
                !plainText.toLowerCase().includes("giảm"));

            let cellClass = "financial-td";
            if (NUMERIC_CELL.test(plainText)) cellClass += " cell-num"; // figures stay on one line with their citation; names and sentences wrap
            if (isDashOrNA) cellClass += " cell-empty";
            else if (isDeltaNegative) cellClass += " delta-negative";
            else if (isDeltaPositive) cellClass += " delta-positive";

            return (
              <td className={cellClass} style={style}>
                {processChildren(children)}
              </td>
            );
          },
          strong: ({ children }) => (
            <strong className="markdown-highlight-bold">{processChildren(children)}</strong>
          ),
          p: ({ children }) => {
            const rawText = getPlainText(children).trim();
            // Special styling if paragraph is a verification note: ⚠️
            if (rawText.startsWith("⚠️")) {
              return (
                <div className="markdown-callout-warning">
                  {processChildren(children)}
                </div>
              );
            }
            // Footnote / table note styling: starts with *Note:, Note:, *Ghi chú:, Ghi chú:
            if (
              rawText.startsWith("*Note:") ||
              rawText.startsWith("Note:") ||
              rawText.startsWith("*Ghi chú:") ||
              rawText.startsWith("Ghi chú:") ||
              rawText.startsWith("*Lưu ý:")
            ) {
              return (
                <p className="markdown-table-footnote">
                  {processChildren(children)}
                </p>
              );
            }
            return <p className="markdown-paragraph">{processChildren(children)}</p>;
          },
          ul: ({ children }) => <ul className="markdown-unordered-list">{children}</ul>,
          ol: ({ children }) => <ol className="markdown-ordered-list">{children}</ol>,
          li: ({ children }) => (
            <li className="markdown-list-item">{processChildren(children)}</li>
          ),
          code: ({ children, className }) => {
            return <code className={`markdown-inline-code ${className || ""}`}>{children}</code>;
          },
          blockquote: ({ children }) => (
            <blockquote className="markdown-blockquote">{children}</blockquote>
          ),
        }}
      >
        {normalizeMarkdown(content)}
      </ReactMarkdown>
    </div>
  );
};

