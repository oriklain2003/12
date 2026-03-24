/**
 * MessageBubble — renders a single chat message.
 * User messages are right-aligned; agent messages are left-aligned with accent border.
 * Streaming messages show a blinking cursor via CSS ::after pseudo-element.
 * Text is rendered with white-space: pre-wrap to preserve line breaks.
 */

import type { ChatMessage } from '../../types/agent';
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

  return (
    <div className={classNames}>
      {message.content}
    </div>
  );
}
