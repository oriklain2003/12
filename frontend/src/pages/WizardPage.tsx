/**
 * WizardPage — full-screen conversational workflow builder.
 * Streams from the build_agent persona via SSE.
 * Handles present_options, show_intent_preview, and generate_workflow tool results.
 */

import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import { streamAgentChat, buildFromPreview } from '../api/agent';
import { WizardChat } from '../components/Wizard/WizardChat';
import type { WizardChatMessage, WizardOptionsData, IntentPreviewData, GenerateWorkflowResult } from '../types/wizard';
import './WizardPage.css';

export function WizardPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<WizardChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isBuilding, setIsBuilding] = useState(false);

  const showWelcome = messages.length === 0;

  useEffect(() => {
    document.title = 'Build Wizard — ONYX 12';
  }, []);

  const addMessage = useCallback((msg: WizardChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateLastAgentMessage = useCallback((content: string) => {
    setMessages((prev) => {
      const msgs = [...prev];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'agent' && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], content: msgs[i].content + content };
          return msgs;
        }
      }
      return prev;
    });
  }, []);

  const clearStreamingFlag = useCallback(() => {
    setMessages((prev) => {
      const msgs = [...prev];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'agent' && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], streaming: false };
          return msgs;
        }
      }
      return prev;
    });
  }, []);

  const handleSend = useCallback(
    async (message: string) => {
      if (!message.trim() || isStreaming) return;

      // 1. Add user message (skip for UI command signals)
      const isCommand = message.startsWith('[') && message.endsWith(']');
      if (!isCommand) {
        addMessage({
          id: crypto.randomUUID(),
          role: 'user',
          content: message,
          timestamp: Date.now(),
        });
      }

      // 2. Add placeholder streaming agent message
      addMessage({
        id: crypto.randomUUID(),
        role: 'agent',
        content: '',
        timestamp: Date.now(),
        streaming: true,
      });

      // 3. Start streaming
      setIsStreaming(true);

      try {
        const stream = streamAgentChat(
          message,
          sessionId,
          null,
          null,
          'general',
          null,
          null,
          'build_agent',
        );

        for await (const event of stream) {
          if (!event.type) continue;

          if (event.type === 'session') {
            const sessionData = event.data as Record<string, unknown>;
            setSessionId(sessionData.session_id as string);
          } else if (event.type === 'text') {
            // Remove thinking indicator when real text starts
            setMessages((prev) => {
              const filtered = prev.filter((m) => m.type !== 'thinking');
              return filtered;
            });
            updateLastAgentMessage(event.data as string);
          } else if (event.type === 'thinking') {
            setMessages((prev) => {
              const msgs = [...prev];
              const last = msgs[msgs.length - 1];
              if (last?.type === 'thinking') {
                msgs[msgs.length - 1] = {
                  ...last,
                  content: last.content + (event.data as string),
                };
                return msgs;
              }
              return [
                ...msgs,
                {
                  id: crypto.randomUUID(),
                  role: 'agent' as const,
                  content: event.data as string,
                  timestamp: Date.now(),
                  type: 'thinking',
                },
              ];
            });
          } else if (event.type === 'tool_call') {
            const toolData = event.data as Record<string, unknown>;
            addMessage({
              id: crypto.randomUUID(),
              role: 'agent',
              content: '',
              timestamp: Date.now(),
              type: 'tool_call',
              toolName: toolData.name as string,
            });
          } else if (event.type === 'tool_result') {
            const resultData = event.data as Record<string, unknown>;
            const toolName = resultData?.name as string | undefined;
            const toolResult = resultData?.result as Record<string, unknown> | undefined;

            // Mark last matching tool_call as done
            setMessages((prev) => {
              const msgs = [...prev];
              for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].type === 'tool_call' && msgs[i].toolName === toolName && !msgs[i].content) {
                  const updates: Partial<WizardChatMessage> = { content: 'done' };
                  // For plan_verification, store the result status for the banner
                  if (toolName === 'plan_verification' && toolResult) {
                    updates.verificationResult = (toolResult.status as string) === 'issues_found'
                      ? 'issues_found'
                      : 'passed';
                  }
                  msgs[i] = { ...msgs[i], ...updates };
                  return msgs;
                }
              }
              return prev;
            });

            if (toolName === 'present_options' && toolResult) {
              addMessage({
                id: crypto.randomUUID(),
                role: 'agent',
                content: '',
                timestamp: Date.now(),
                type: 'options',
                toolData: toolResult as unknown as WizardOptionsData,
              });
            } else if (toolName === 'show_intent_preview' && toolResult) {
              addMessage({
                id: crypto.randomUUID(),
                role: 'agent',
                content: '',
                timestamp: Date.now(),
                type: 'preview',
                toolData: toolResult as unknown as IntentPreviewData,
              });
            } else if (toolName === 'generate_workflow' && toolResult) {
              const result = toolResult as unknown as GenerateWorkflowResult;
              if (result.status === 'created' && result.workflow_id) {
                toast.success('Workflow created — loading canvas...');
                const workflowId = result.workflow_id;
                setTimeout(() => {
                  navigate(`/workflow/${workflowId}`);
                }, 800);
              } else if (result.status === 'validation_failed') {
                const errorSummary = result.errors
                  ? result.errors.map((e) => e.message).join('; ')
                  : 'The workflow has connection issues. You can try again or adjust your requirements.';
                addMessage({
                  id: crypto.randomUUID(),
                  role: 'agent',
                  content: `Couldn't generate a valid workflow\n\n${errorSummary}`,
                  timestamp: Date.now(),
                  type: 'error',
                });
              }
            }
          } else if (event.type === 'error') {
            const errData = event.data as Record<string, unknown> | string;
            const errMsg =
              typeof errData === 'string'
                ? errData
                : ((errData?.message as string) ?? 'Agent encountered an error');
            toast.error(errMsg);
            break;
          } else if (event.type === 'done') {
            clearStreamingFlag();
            setIsStreaming(false);
          }
        }
      } catch {
        toast.error('Connection lost — please try again');
      } finally {
        clearStreamingFlag();
        setIsStreaming(false);
      }
    },
    [isStreaming, sessionId, addMessage, updateLastAgentMessage, clearStreamingFlag, navigate]
  );

  const handleBuildWorkflow = useCallback(async () => {
    if (!sessionId || isBuilding) return;
    setIsBuilding(true);

    try {
      const result = await buildFromPreview(sessionId);

      if (result.status === 'created' && result.workflow_id) {
        toast.success('Workflow created — loading canvas...');
        setTimeout(() => {
          navigate(`/workflow/${result.workflow_id}`);
        }, 800);
      } else if (result.status === 'validation_failed') {
        const errorSummary = result.errors
          ? result.errors.map((e) => e.message).join('; ')
          : 'The workflow has connection issues.';
        addMessage({
          id: crypto.randomUUID(),
          role: 'agent',
          content: `Couldn't generate a valid workflow\n\n${errorSummary}`,
          timestamp: Date.now(),
          type: 'error',
        });
      } else {
        toast.error(result.message ?? 'Failed to build workflow');
      }
    } catch {
      toast.error('Failed to build workflow — please try again');
    } finally {
      setIsBuilding(false);
    }
  }, [sessionId, isBuilding, navigate, addMessage]);

  const handleAdjustPlan = useCallback(() => {
    handleSend('[ADJUST_PLAN]');
  }, [handleSend]);

  return (
    <div className="wizard-page">
      <Toaster position="bottom-right" theme="dark" />

      <header className="wizard-header">
        <div className="wizard-header__brand">
          <img src="/onyx-logo.svg" alt="ONYX" className="wizard-header__logo" />
          <span className="wizard-header__divider" />
          <span className="wizard-header__product">12</span>
        </div>
        <button
          className="wizard-header__back"
          onClick={() => navigate('/')}
          type="button"
        >
          Back to Workflows
        </button>
      </header>

      <div className="wizard-content">
        <WizardChat
          messages={messages}
          showWelcome={showWelcome}
          isStreaming={isStreaming}
          isBuilding={isBuilding}
          onSend={(msg) => { void handleSend(msg); }}
          onBuildWorkflow={handleBuildWorkflow}
          onAdjustPlan={handleAdjustPlan}
        />
      </div>
    </div>
  );
}
