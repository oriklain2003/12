/**
 * WizardInput — textarea with auto-expand and send button for the Wizard chat.
 * Matches ChatInput pattern with wizard-specific placeholder.
 */

import { useState, useRef, useCallback } from 'react';
import './WizardInput.css';

interface WizardInputProps {
  onSend: (message: string) => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function WizardInput({ onSend, isStreaming, disabled }: WizardInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleInput = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    const lineHeight = 20;
    const maxLines = 5;
    const maxHeight = lineHeight * maxLines + 24; // padding
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, isStreaming, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const sendDisabled = !input.trim() || isStreaming || disabled;

  return (
    <div className="wizard-input">
      <textarea
        ref={textareaRef}
        className="wizard-input__textarea"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="Describe your analysis idea..."
        rows={1}
        readOnly={isStreaming}
        aria-label="Wizard message"
      />
      <button
        className={`glass-btn glass-btn--accent wizard-input__send-btn${isStreaming ? ' wizard-input__send-btn--streaming' : ''}`}
        onClick={handleSend}
        disabled={sendDisabled}
        aria-label="Send message"
        title="Send (Enter)"
      >
        {isStreaming ? (
          <span className="wizard-input__pulse-dot" />
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M8 13V3M3 8l5-5 5 5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>
    </div>
  );
}
