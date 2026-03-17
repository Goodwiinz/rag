'use client';

import React, { useEffect, useCallback, useRef, useState } from 'react';
import { AgentFAB } from './AgentFAB';
import { AgentPanel } from './AgentPanel';
import { AgentSidebar } from './AgentSidebar';
import { useAgentChatStore } from '@/store/agentChatStore';
import { usePageContext } from '@/hooks/usePageContext';

const MIN_WIDTH = 320;
const MAX_WIDTH_RATIO = 0.5; // never exceed 50% of viewport
const DEFAULT_WIDTH = 420;
const MIN_CONTENT_WIDTH = 480; // main content never narrower than this
const COLLAPSE_BREAKPOINT = MIN_WIDTH + MIN_CONTENT_WIDTH; // auto-collapse below this
const STORAGE_KEY = 'agent-sidebar-width';

function getStoredWidth(): number {
  if (typeof window === 'undefined') return DEFAULT_WIDTH;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    const n = parseInt(stored, 10);
    if (!isNaN(n) && n >= MIN_WIDTH) return n;
  }
  return DEFAULT_WIDTH;
}

/** Clamp sidebar width to respect viewport and minimum content area. */
function clampWidth(desired: number, viewportWidth: number): number {
  const maxByRatio = Math.floor(viewportWidth * MAX_WIDTH_RATIO);
  const maxByContent = viewportWidth - MIN_CONTENT_WIDTH;
  const max = Math.max(MIN_WIDTH, Math.min(maxByRatio, maxByContent));
  return Math.max(MIN_WIDTH, Math.min(desired, max));
}

export function GlobalAgentChat() {
  const uiMode = useAgentChatStore((s) => s.uiMode);
  const messages = useAgentChatStore((s) => s.messages);
  const isStreaming = useAgentChatStore((s) => s.isStreaming);
  const inputValue = useAgentChatStore((s) => s.inputValue);
  const pageContext = useAgentChatStore((s) => s.pageContext);
  const close = useAgentChatStore((s) => s.close);
  const openSidebar = useAgentChatStore((s) => s.openSidebar);
  const openPanel = useAgentChatStore((s) => s.openPanel);
  const setInputValue = useAgentChatStore((s) => s.setInputValue);
  const sendMessage = useAgentChatStore((s) => s.sendMessage);
  const stopGeneration = useAgentChatStore((s) => s.stopGeneration);
  const clearMessages = useAgentChatStore((s) => s.clearMessages);
  const newThread = useAgentChatStore((s) => s.newThread);
  const setPageContext = useAgentChatStore((s) => s.setPageContext);

  // Sidebar width state
  const [sidebarWidth, setSidebarWidth] = useState(getStoredWidth);
  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);
  // Track whether user manually chose panel mode (prevents auto-expand fighting)
  const userChosePanel = useRef(false);

  // Auto-detect and update page context
  const detectedContext = usePageContext();
  useEffect(() => {
    setPageContext(detectedContext);
  }, [detectedContext, setPageContext]);

  // --- Viewport-aware auto-adjust (VS Code behavior) ---
  useEffect(() => {
    if (typeof window === 'undefined') return;

    function handleResize() {
      const vw = window.innerWidth;

      // Auto-collapse: viewport too narrow for sidebar + content
      if (uiMode === 'sidebar' && vw < COLLAPSE_BREAKPOINT) {
        userChosePanel.current = false; // viewport-driven, not user-driven
        openPanel();
        return;
      }

      // Auto-expand back to sidebar when viewport grows wide enough
      // (only if the collapse was viewport-driven, not user-initiated)
      if (
        uiMode === 'panel' &&
        !userChosePanel.current &&
        vw >= COLLAPSE_BREAKPOINT
      ) {
        openSidebar();
        return;
      }

      // Re-clamp width on viewport resize
      if (uiMode === 'sidebar') {
        setSidebarWidth((prev) => clampWidth(prev, vw));
      }
    }

    window.addEventListener('resize', handleResize);
    // Run once on mount to handle initial viewport
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, [uiMode, openPanel, openSidebar]);

  // Reset user-chose-panel flag when sidebar opens or chat closes
  useEffect(() => {
    if (uiMode === 'sidebar' || uiMode === 'closed') {
      userChosePanel.current = false;
    }
  }, [uiMode]);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        useAgentChatStore.getState().toggle();
      }
      if (e.key === 'Escape' && uiMode !== 'closed') {
        close();
      }
    },
    [uiMode, close]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // --- Drag-to-resize handlers ---
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isDragging.current = true;
      startX.current = e.clientX;
      startWidth.current = sidebarWidth;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [sidebarWidth]
  );

  useEffect(() => {
    function handleMouseMove(e: MouseEvent) {
      if (!isDragging.current) return;
      // Dragging left → wider sidebar
      const delta = startX.current - e.clientX;
      const desired = startWidth.current + delta;
      const clamped = clampWidth(desired, window.innerWidth);
      setSidebarWidth(clamped);
    }

    function handleMouseUp() {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      // Persist width
      localStorage.setItem(STORAGE_KEY, String(sidebarWidth));
    }

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [sidebarWidth]);

  return (
    <>
      {/* Mobile backdrop */}
      {uiMode !== 'closed' && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          aria-hidden="true"
          onClick={close}
        />
      )}

      {/* Panel mode — floating popup (used on narrow viewports or when collapsed) */}
      {uiMode === 'panel' && (
        <div
          className="fixed bottom-[88px] right-6 z-50 w-[400px] h-[560px] max-sm:w-full max-sm:h-[100dvh] max-sm:bottom-0 max-sm:left-0 max-sm:right-0 max-sm:rounded-b-none max-sm:rounded-t-xl bg-background border border-border rounded-xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200"
          role="dialog"
          aria-modal="true"
          aria-label="Agent chat panel"
          aria-labelledby="agent-panel-title"
        >
          <AgentPanel
            messages={messages}
            isStreaming={isStreaming}
            inputValue={inputValue}
            pageContext={pageContext}
            onInputChange={setInputValue}
            onSend={() => void sendMessage()}
            onStop={stopGeneration}
            onClear={clearMessages}
            onClose={close}
            onExpand={() => {
              userChosePanel.current = false;
              openSidebar();
            }}
            onNewThread={newThread}
          />
        </div>
      )}

      {/* Sidebar mode — flex layout child, pushes content aside */}
      {uiMode === 'sidebar' && (
        <div
          className="h-full shrink-0 overflow-hidden bg-background border-l border-border relative"
          style={{ width: sidebarWidth }}
          role="complementary"
          aria-label="Agent chat sidebar"
        >
          {/* Drag handle — wide hit area, narrow visible indicator */}
          <div
            onMouseDown={handleMouseDown}
            className="absolute left-0 top-0 bottom-0 w-3 cursor-col-resize z-10 group/handle"
            aria-label="Resize sidebar"
            role="separator"
            aria-orientation="vertical"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1 bg-transparent group-hover/handle:bg-primary/30 group-active/handle:bg-primary/50 transition-colors" />
          </div>
          <AgentSidebar
            onCollapse={() => {
              userChosePanel.current = true;
              openPanel();
            }}
          />
        </div>
      )}

      {/* FAB */}
      <AgentFAB />
    </>
  );
}
