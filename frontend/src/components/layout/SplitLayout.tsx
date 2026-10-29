import React, { useState, useEffect } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "../common/Icons";
import "./layout.css";

interface SplitLayoutProps {
  sidebar: React.ReactNode;
  main: React.ReactNode;
  evidencePane?: React.ReactNode;
  isEvidenceOpen?: boolean;
}

export const SplitLayout: React.FC<SplitLayoutProps> = ({
  sidebar,
  main,
  evidencePane,
  isEvidenceOpen = false,
}) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth > 900;
    }
    return true;
  });

  // Keyboard shortcut Ctrl+B / Cmd+B to toggle sidebar (ChatGPT/VSCode standard)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setIsSidebarOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="split-layout">
      {/* Mobile Sidebar Overlay Backdrop */}
      {isSidebarOpen && (
        <div
          className="split-sidebar-backdrop"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* 1. Left Sidebar: Chat Sessions History (Claude / ChatGPT Style) */}
      <aside className={`split-sidebar ${!isSidebarOpen ? "collapsed" : ""}`}>
        {sidebar}
      </aside>

      {/* Toggle Sidebar Button */}
      <button
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        title={isSidebarOpen ? "Thu gọn danh sách chat (Ctrl+B)" : "Mở danh sách chat (Ctrl+B)"}
        className={`split-toggle-btn ${!isSidebarOpen ? "collapsed" : ""}`}
      >
        {isSidebarOpen ? <ChevronLeftIcon size={12} /> : <ChevronRightIcon size={12} />}
      </button>

      {/* 2. Main Workspace: Active Document Banner & Chat Stream */}
      <main className="split-main">
        {main}
      </main>

      {/* 3. Right Evidence Panel: Source Grounding Inspector (NotebookLM Style) */}
      {evidencePane && (
        <aside className={`split-evidence ${!isEvidenceOpen ? "closed" : ""}`}>
          {evidencePane}
        </aside>
      )}
    </div>
  );
};
