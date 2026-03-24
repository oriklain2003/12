/**
 * MessageList — scrollable thread of chat messages.
 * Auto-scrolls to bottom when new messages are added.
 * Shows empty state with mode-specific copy when no messages exist.
 */

import { useRef, useEffect } from 'react';
import { useFlowStore } from '../../store/flowStore';
import { MessageBubble } from './MessageBubble';
import { DiffProposal } from './DiffProposal';
import { ToolCallIndicator } from './ToolCallIndicator';
import './ChatPanel.css';

const EMPTY_STATE_BODY: Record<string, string> = {
  general: 'Ask me about your workflow, find cubes, or suggest improvements.',
  optimize: "Describe a performance or simplification goal and I'll suggest changes to the canvas.",
  fix: 'Run your workflow first, then I can read the errors and help diagnose.',
};

export function MessageList() {
  const chatMessages = useFlowStore((s) => s.chatMessages);
  const chatPanelMode = useFlowStore((s) => s.chatPanelMode);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [chatMessages.length]);

  if (chatMessages.length === 0) {
    return (
      <div className="message-list" ref={containerRef}>
        <div className="chat-panel__empty">
          <span className="chat-panel__empty-heading">No messages yet</span>
          <span className="chat-panel__empty-body">
            {EMPTY_STATE_BODY[chatPanelMode] ?? EMPTY_STATE_BODY.general}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={containerRef}>
      {chatMessages.map((message) => {
        if (message.type === 'tool_call') {
          return (
            <ToolCallIndicator
              key={message.id}
              toolName={message.toolName ?? ''}
            />
          );
        }

        if (message.diff) {
          return (
            <div key={message.id}>
              <MessageBubble message={message} />
              <DiffProposal diff={message.diff} />
            </div>
          );
        }

        return <MessageBubble key={message.id} message={message} />;
      })}
    </div>
  );
}
