/**
 * WizardChat — scrollable chat column with message rendering and input.
 * Centers at max-width 720px. Shows WizardWelcome when no messages exist.
 */

import { useEffect, useRef } from 'react';
import { MessageBubble } from '../Chat/MessageBubble';
import { ToolCallIndicator } from '../Chat/ToolCallIndicator';
import { WizardWelcome } from './WizardWelcome';
import { WizardInput } from './WizardInput';
import { OptionCards } from './OptionCards';
import { MiniGraph } from './MiniGraph';
import type { WizardChatMessage, WizardOptionsData, IntentPreviewData } from '../../types/wizard';
import './WizardChat.css';

interface WizardChatProps {
  messages: WizardChatMessage[];
  showWelcome: boolean;
  isStreaming: boolean;
  onSend: (message: string) => void;
  onBuildWorkflow: () => void;
  onAdjustPlan: () => void;
}

export function WizardChat({
  messages,
  showWelcome,
  isStreaming,
  onSend,
  onBuildWorkflow,
  onAdjustPlan,
}: WizardChatProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="wizard-chat">
      <div className="wizard-chat__content">
        {showWelcome && <WizardWelcome onSelect={onSend} />}

        {!showWelcome && (
          <div className="wizard-chat__messages">
            {messages.map((msg) => {
              if (msg.role === 'user') {
                return (
                  <MessageBubble
                    key={msg.id}
                    message={{
                      id: msg.id,
                      role: msg.role,
                      content: msg.content,
                      timestamp: msg.timestamp,
                      type: msg.type,
                      toolName: msg.toolName,
                      streaming: msg.streaming,
                    }}
                  />
                );
              }

              if (msg.type === 'tool_call') {
                return (
                  <ToolCallIndicator
                    key={msg.id}
                    toolName={msg.toolName ?? ''}
                    done={msg.content === 'done'}
                  />
                );
              }

              if (msg.type === 'thinking') {
                return (
                  <div key={msg.id} className="wizard-chat__thinking">
                    {msg.content || 'Thinking...'}
                  </div>
                );
              }

              if (msg.type === 'options' && msg.toolData) {
                return (
                  <OptionCards
                    key={msg.id}
                    data={msg.toolData as WizardOptionsData}
                    onSelect={onSend}
                    disabled={isStreaming}
                  />
                );
              }

              if (msg.type === 'preview' && msg.toolData) {
                return (
                  <MiniGraph
                    key={msg.id}
                    data={msg.toolData as IntentPreviewData}
                    onBuild={onBuildWorkflow}
                    onAdjust={onAdjustPlan}
                    disabled={isStreaming}
                  />
                );
              }

              if (msg.type === 'error') {
                return (
                  <div key={msg.id} className="wizard-chat__error-block">
                    <p className="wizard-chat__error-text">{msg.content}</p>
                    <button
                      className="glass-btn wizard-chat__retry-btn"
                      onClick={() => onSend('Please try again')}
                      type="button"
                      style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px' }}
                    >
                      Retry Generation
                    </button>
                  </div>
                );
              }

              // Default agent text message
              return (
                <MessageBubble
                  key={msg.id}
                  message={{
                    id: msg.id,
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.timestamp,
                    type: msg.type,
                    toolName: msg.toolName,
                    streaming: msg.streaming,
                  }}
                />
              );
            })}
            <div ref={bottomRef} />
          </div>
        )}

        <WizardInput onSend={onSend} isStreaming={isStreaming} />
      </div>
    </div>
  );
}
