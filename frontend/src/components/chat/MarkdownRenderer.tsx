import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationItem } from "../../types/chat";

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
              ? `Xem nguồn tại Trang ${targetCitation.page}`
              : `Trích dẫn nguồn [${citeNum}]`
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
    let normalized = raw.replace(/([^\n|])\n(\|[^\n]+\|)/g, "$1\n\n$2");
    normalized = normalized.replace(/(\|[^\n]+\|)\n([^\n|])/g, "$1\n\n$2");
    return normalized;
  };

  return (
    <div className="markdown-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
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
              {processChildren(children)}
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
              plainText.toLowerCase().includes("giảm");
            const isDeltaPositive =
              plainText.startsWith("+") ||
              (plainText.includes("%") &&
                !plainText.startsWith("-") &&
                !plainText.startsWith("−") &&
                !plainText.toLowerCase().includes("giảm"));

            let cellClass = "financial-td";
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
            // Footnote / table note styling: starts with *Ghi chú:, Ghi chú:, *Lưu ý:
            if (
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

