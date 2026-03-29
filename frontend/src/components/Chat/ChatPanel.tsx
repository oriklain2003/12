/**
 * ChatPanel — right sidebar shell for the Canvas Agent chat interface.
 *
 * - Reads chatPanelOpen, chatPanelMode from flowStore
 * - Renders nothing when closed (not an icon strip — per UI-SPEC)
 * - Resizable via drag handle on the left edge
 * - Contains header (title + mode toggle + close button), message list, and chat input
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { ModeToggle } from './ModeToggle';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import './ChatPanel.css';

export function ChatPanel() {
  const chatPanelOpen = useFlowStore((s) => s.chatPanelOpen);
  const setChatPanelOpen = useFlowStore((s) => s.setChatPanelOpen);
  const clearChat = useFlowStore((s) => s.clearChat);
  const isAgentStreaming = useFlowStore((s) => s.isAgentStreaming);
  const chatPersona = useFlowStore((s) => s.chatPersona);

  const [width, setWidth] = useState(320);
  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    startX.current = e.clientX;
    startWidth.current = width;
    e.preventDefault();
  }, [width]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = startX.current - e.clientX;
      const newWidth = Math.min(480, Math.max(240, startWidth.current + delta));
      setWidth(newWidth);
    };

    const handleMouseUp = () => {
      isDragging.current = false;
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  if (!chatPanelOpen) return null;

  return (
    <div className="chat-panel" style={{ width }}>
      <div
        className="chat-panel__drag-handle"
        onMouseDown={handleMouseDown}
        aria-hidden="true"
      />

      <div className="chat-panel__header">
        <span className="chat-panel__title">
          {chatPersona === 'results_followup' ? 'Q&A' : 'AGENT'}
        </span>
        <ModeToggle />
        <button
          className="chat-panel__new-chat-btn"
          onClick={clearChat}
          disabled={isAgentStreaming}
          aria-label="New chat"
          title="New chat"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d="M7 2.5v9M2.5 7h9"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
        <button
          className="chat-panel__close-btn"
          onClick={() => setChatPanelOpen(false)}
          aria-label="Close agent panel"
          title="Close"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path
              d="M2 2l10 10M12 2L2 12"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>

      <div className="chat-panel__body">
        <MessageList />
        <ChatInput />
      </div>
    </div>
  );
}
