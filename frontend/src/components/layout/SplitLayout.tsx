import React, { useEffect } from "react";
import "./layout.css";

interface SplitLayoutProps {
  sidebar: React.ReactNode;
  /** The top bar of the work area (it sits right of the sidebar, not above it). */
  header: React.ReactNode;
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
  header,
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

  return (
    <div className="split-layout">
      {/* Mobile Sidebar Overlay Backdrop */}
      {isSidebarOpen && (
        <div
          className="split-sidebar-backdrop"
          onClick={() => onToggleSidebar?.()}
        />
      )}

      {/* 1. Left Sidebar: brand, chats, sign-in card (full height, navy) */}
      <aside className={`split-sidebar ${!isSidebarOpen ? "collapsed" : ""}`}>
        {sidebar}
      </aside>

      <div className="split-workspace">
        {header}

        <div className="split-body">
          {/* 2. Main Workspace: Chat Stream (takes the width the panels leave) */}
          <main className="split-main">
            {main}
          </main>

          {/* 3. Sources Drawer: Session-Scoped Documents Manager */}
          {sourcesPane && (
            <aside className={`split-sources-pane ${!isSourcesOpen ? "closed" : ""}`}>
              {sourcesPane}
            </aside>
          )}

          {/* 4. Source preview: the original PDF page next to the answer */}
          {pdfViewerPane && (
            <section className={`split-pdf-pane ${!isSplitViewOpen ? "closed" : ""}`}>
              {pdfViewerPane}
            </section>
          )}
        </div>
      </div>
    </div>
  );
};
