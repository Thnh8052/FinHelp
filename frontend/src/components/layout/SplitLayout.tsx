import React, { useEffect } from "react";
import "./layout.css";

interface SplitLayoutProps {
  sidebar: React.ReactNode;
  main: React.ReactNode;
  sourcesPane?: React.ReactNode;
  isSourcesOpen?: boolean;
  pdfViewerPane?: React.ReactNode;
  isSplitViewOpen?: boolean;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}

export const SplitLayout: React.FC<SplitLayoutProps> = ({
  sidebar,
  main,
  sourcesPane,
  isSourcesOpen = false,
  pdfViewerPane,
  isSplitViewOpen = false,
  isSidebarOpen = true,
  onToggleSidebar,
}) => {
  // Keyboard shortcut Ctrl+B / Cmd+B to toggle sidebar (ChatGPT/VSCode standard)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        onToggleSidebar?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onToggleSidebar]);

  // Compute dynamic width modifier for Main Chat workspace
  let mainLayoutClass = "flex-full";
  if (isSplitViewOpen && isSourcesOpen) {
    mainLayoutClass = "chat-both-open"; // ~38% width
  } else if (isSplitViewOpen && !isSourcesOpen) {
    mainLayoutClass = "chat-split-open"; // ~45% width
  } else if (!isSplitViewOpen && isSourcesOpen) {
    mainLayoutClass = "chat-sources-open"; // flex-1 alongside sources
  }

  return (
    <div className="split-layout">
      {/* Mobile Sidebar Overlay Backdrop */}
      {isSidebarOpen && (
        <div
          className="split-sidebar-backdrop"
          onClick={() => onToggleSidebar?.()}
        />
      )}

      {/* 1. Left Sidebar: Chat Sessions History */}
      <aside className={`split-sidebar ${!isSidebarOpen ? "collapsed" : ""}`}>
        {sidebar}
      </aside>

      {/* 2. Main Workspace: Chat Stream */}
      <main className={`split-main ${mainLayoutClass}`}>
        {main}
      </main>

      {/* 3. Sources Drawer: Session-Scoped Documents Manager (~320px) */}
      {sourcesPane && (
        <aside className={`split-sources-pane ${!isSourcesOpen ? "closed" : ""}`}>
          {sourcesPane}
        </aside>
      )}

      {/* 4. PDF Split-View Pane: Audited Financial Statements Reader (~50-55%) */}
      {pdfViewerPane && (
        <section className={`split-pdf-pane ${!isSplitViewOpen ? "closed" : ""}`}>
          {pdfViewerPane}
        </section>
      )}
    </div>
  );
};
