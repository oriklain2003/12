/**
 * ChatInput — textarea with Send button for the Canvas Agent chat panel.
 *
 * Handles the full SSE send flow:
 * 1. User types and presses Enter or Send button
 * 2. User message added to store, placeholder agent message added (streaming: true)
 * 3. streamAgentChat generator is iterated
 * 4. SSE events update last streaming agent message, capture session ID, detect diffs
 * 5. On done/error: streaming flag cleared
 */

import { useState, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import { useFlowStore, serializeGraph } from '../../store/flowStore';
import { streamAgentChat } from '../../api/agent';
import type { AgentDiff } from '../../types/agent';
import './ChatPanel.css';

const PLACEHOLDER: Record<string, string> = {
  general: 'Ask about your workflow...',
  optimize: 'Describe what you want to optimize...',
  fix: 'Describe the issue or let me diagnose...',
};

export function ChatInput() {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isAgentStreaming = useFlowStore((s) => s.isAgentStreaming);
  const chatPanelMode = useFlowStore((s) => s.chatPanelMode);
  const chatPersona = useFlowStore((s) => s.chatPersona);
  const chatSessionId = useFlowStore((s) => s.chatSessionId);
  const workflowId = useFlowStore((s) => s.workflowId);
  const nodes = useFlowStore((s) => s.nodes);
  const edges = useFlowStore((s) => s.edges);
  const executionStatus = useFlowStore((s) => s.executionStatus);
  const results = useFlowStore((s) => s.results);

  const handleInput = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isAgentStreaming) return;

    const store = useFlowStore.getState();

    // 1. Add user message
    store.addChatMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    });

    // 2. Clear input field and reset height
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // 3. Add placeholder streaming agent message
    store.addChatMessage({
      id: crypto.randomUUID(),
      role: 'agent',
      content: '',
      timestamp: Date.now(),
      streaming: true,
    });

    // 4. Start streaming
    store.setIsAgentStreaming(true);

    // 5. Serialize graph
    const graph = serializeGraph(nodes, edges);

    // 6. Build execution errors from status
    const errors = Object.fromEntries(
      Object.entries(executionStatus)
        .filter(([, s]) => s.status === 'error')
        .map(([id, s]) => [id, { status: s.status, error: s.error }])
    );

    try {
      const stream = streamAgentChat(
        trimmed,
        chatSessionId,
        workflowId,
        graph,
        chatPanelMode,
        Object.keys(errors).length > 0 ? errors : null,
        Object.keys(results).length > 0 ? (results as Record<string, unknown>) : null,
        chatPersona,
      );

      for await (const event of stream) {
        if (!event.type) continue; // skip malformed/ping events

        if (event.type === 'session') {
          const sessionData = event.data as Record<string, unknown>;
          useFlowStore.getState().setChatSessionId(sessionData.session_id as string);
        } else if (event.type === 'text') {
          // Remove thinking indicator when real text starts
          const msgs = useFlowStore.getState().chatMessages;
          const filtered = msgs.filter((m) => m.type !== 'thinking');
          if (filtered.length !== msgs.length) {
            useFlowStore.setState({ chatMessages: filtered });
          }
          useFlowStore.getState().updateLastAgentMessage(event.data as string);
        } else if (event.type === 'thinking') {
          // Show/update thinking indicator in the message list
          const store = useFlowStore.getState();
          const lastMsg = store.chatMessages[store.chatMessages.length - 1];
          if (lastMsg?.type === 'thinking') {
            const msgs = [...store.chatMessages];
            msgs[msgs.length - 1] = { ...lastMsg, content: lastMsg.content + (event.data as string) };
            useFlowStore.setState({ chatMessages: msgs });
          } else {
            store.addChatMessage({
              id: crypto.randomUUID(),
              role: 'agent',
              content: event.data as string,
              timestamp: Date.now(),
              type: 'thinking',
            });
          }
        } else if (event.type === 'tool_call') {
          const toolData = event.data as Record<string, unknown>;
          useFlowStore.getState().addChatMessage({
            id: crypto.randomUUID(),
            role: 'agent',
            content: '',
            timestamp: Date.now(),
            type: 'tool_call',
            toolName: toolData.name as string,
          });
        } else if (event.type === 'tool_result') {
          // Mark the last tool_call as completed (stop spinner) instead of removing it
          const currentMsgs = useFlowStore.getState().chatMessages;
          const msgs = [...currentMsgs];
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].type === 'tool_call' && !msgs[i].content) {
              msgs[i] = { ...msgs[i], content: 'done' };
              useFlowStore.setState({ chatMessages: msgs });
              break;
            }
          }

          const resultData = event.data as Record<string, unknown>;
          // proposed_diff is nested under result: {name, result: {proposed_diff: ...}}
          const toolResult = resultData?.result as Record<string, unknown> | undefined;
          if (toolResult && 'proposed_diff' in toolResult) {
            const diff = toolResult.proposed_diff as AgentDiff;
            useFlowStore.getState().setPendingDiff(diff);
            // Update the last streaming agent message to carry the diff
            const msgs = [...useFlowStore.getState().chatMessages];
            for (let i = msgs.length - 1; i >= 0; i--) {
              if (msgs[i].role === 'agent' && msgs[i].streaming) {
                msgs[i] = { ...msgs[i], diff };
                useFlowStore.setState({ chatMessages: msgs });
                break;
              }
            }
          }
        } else if (event.type === 'error') {
          const errData = event.data as Record<string, unknown> | string;
          const errMsg = typeof errData === 'string'
            ? errData
            : (errData?.message as string) ?? 'Agent encountered an error';
          toast.error(errMsg);
          break;
        } else if (event.type === 'done') {
          // Mark last streaming message as not streaming
          const currentStore = useFlowStore.getState();
          const msgs = [...currentStore.chatMessages];
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === 'agent' && msgs[i].streaming) {
              msgs[i] = { ...msgs[i], streaming: false };
              useFlowStore.setState({ chatMessages: msgs });
              break;
            }
          }
          useFlowStore.getState().setIsAgentStreaming(false);
        }
      }
    } catch {
      toast.error('Connection lost — please try again');
    } finally {
      // Always clean up streaming state — handles both normal completion
      // and cases where stream ends without a 'done' event
      const finalStore = useFlowStore.getState();
      if (finalStore.isAgentStreaming) {
        const msgs = [...finalStore.chatMessages];
        for (let i = msgs.length - 1; i >= 0; i--) {
          if (msgs[i].role === 'agent' && msgs[i].streaming) {
            msgs[i] = { ...msgs[i], streaming: false };
            useFlowStore.setState({ chatMessages: msgs });
            break;
          }
        }
        finalStore.setIsAgentStreaming(false);
      }
    }
  }, [
    input,
    isAgentStreaming,
    chatSessionId,
    workflowId,
    nodes,
    edges,
    executionStatus,
    results,
    chatPanelMode,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void handleSend();
      }
      // Shift+Enter falls through and inserts newline naturally
    },
    [handleSend]
  );

  const placeholder = PLACEHOLDER[chatPanelMode] ?? PLACEHOLDER.general;
  const sendDisabled = !input.trim() || isAgentStreaming;

  return (
    <div className="chat-input">
      <textarea
        ref={textareaRef}
        className="chat-input__textarea"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={1}
        aria-label="Chat message"
      />
      <button
        className="glass-btn glass-btn--accent chat-input__send-btn"
        onClick={() => void handleSend()}
        disabled={sendDisabled}
        aria-label="Send message"
        title="Send (Enter)"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path
            d="M6 10V2M2 6l4-4 4 4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
