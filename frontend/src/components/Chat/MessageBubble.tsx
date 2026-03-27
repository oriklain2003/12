/**
 * MessageBubble — renders a single chat message.
 * User messages are right-aligned; agent messages are left-aligned with accent border.
 * Streaming messages show a blinking cursor via CSS ::after pseudo-element.
 * Agent messages parse inline markdown (bold, italic, code, lists, paragraphs).
 */

import { useMemo } from 'react';
import type { ChatMessage } from '../../types/agent';
import { renderMarkdown } from '../../utils/renderMarkdown';
import './ChatPanel.css';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.streaming === true;

  const classNames = [
    'message-bubble',
    isUser ? 'message-bubble--user' : 'message-bubble--agent',
    isStreaming ? 'message-bubble--streaming' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const rendered = useMemo(
    () => (!isUser ? renderMarkdown(message.content) : null),
    [message.content, isUser],
  );

  return (
    <div className={classNames}>
      {isUser ? message.content : rendered}
    </div>
  );
}
