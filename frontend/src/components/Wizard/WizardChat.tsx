/**
 * WizardChat — scrollable chat column with message rendering and input.
 * Centers at max-width 860px. Shows WizardWelcome when no messages exist.
 */

import { useEffect, useRef } from 'react';
import { MessageBubble } from '../Chat/MessageBubble';
import { ToolCallIndicator } from '../Chat/ToolCallIndicator';
import { VerificationBanner } from './VerificationBanner';
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
  isBuilding: boolean;
  onSend: (message: string) => void;
  onBuildWorkflow: () => void;
  onAdjustPlan: () => void;
}

/**
 * Determine if a turn separator should be shown before this message.
 * We insert a separator when the role switches from agent→user,
 * giving visual breathing room between conversation turns.
 */
function shouldShowSeparator(messages: WizardChatMessage[], index: number): boolean {
  if (index === 0) return false;
  const current = messages[index];
  const prev = messages[index - 1];
  // Separator before user messages that follow agent content
  return current.role === 'user' && prev.role === 'agent';
}

/**
 * Should we show a role label above this message?
 * Show when the role changes from the previous visible message.
 */
function shouldShowRoleLabel(messages: WizardChatMessage[], index: number): boolean {
  if (index === 0) return true;
  const current = messages[index];
  // Don't show labels for tool_call or thinking — they're inline indicators
  if (current.type === 'tool_call' || current.type === 'thinking') return false;
  // Find previous non-tool/thinking message
  for (let i = index - 1; i >= 0; i--) {
    const prev = messages[i];
    if (prev.type === 'tool_call' || prev.type === 'thinking') continue;
    return current.role !== prev.role;
  }
  return true;
}

export function WizardChat({
  messages,
  showWelcome,
  isStreaming,
  isBuilding,
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
            {messages.map((msg, index) => {
              const separator = shouldShowSeparator(messages, index);
              const roleLabel = shouldShowRoleLabel(messages, index);

              if (msg.role === 'user') {
                return (
                  <div key={msg.id} className="wizard-chat__message-group">
                    {separator && <div className="wizard-chat__turn-separator" />}
                    {roleLabel && (
                      <div className="wizard-chat__role-label wizard-chat__role-label--user">You</div>
                    )}
                    <MessageBubble
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
                  </div>
                );
              }

              if (msg.type === 'tool_call') {
                // Verification gets a dedicated banner instead of the generic indicator
                if (msg.toolName === 'plan_verification') {
                  const verifyStatus = msg.content === 'done'
                    ? (msg.verificationResult === 'issues_found' ? 'issues_found' : 'passed')
                    : 'checking';
                  return (
                    <VerificationBanner
                      key={msg.id}
                      status={verifyStatus as 'checking' | 'passed' | 'issues_found'}
                    />
                  );
                }
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
                    building={isBuilding}
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
                      style={{ fontSize: 14, fontWeight: 600, padding: '10px 20px' }}
                    >
                      Retry Generation
                    </button>
                  </div>
                );
              }

              // Default agent text message
              return (
                <div key={msg.id} className="wizard-chat__message-group">
                  {roleLabel && (
                    <div className="wizard-chat__role-label wizard-chat__role-label--agent">Assistant</div>
                  )}
                  <MessageBubble
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
                </div>
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
