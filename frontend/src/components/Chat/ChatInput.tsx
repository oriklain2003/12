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
      );

      for await (const event of stream) {
        if (event.type === 'session') {
          const sessionData = event.data as Record<string, unknown>;
          useFlowStore.getState().setChatSessionId(sessionData.session_id as string);
        } else if (event.type === 'text') {
          useFlowStore.getState().updateLastAgentMessage(event.data as string);
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
          // Remove the last tool_call indicator now that the result arrived
          const currentMsgs = useFlowStore.getState().chatMessages;
          const withoutToolCall = currentMsgs.filter((m, i) => {
            // Remove last tool_call message
            if (m.type !== 'tool_call') return true;
            // Keep earlier tool_call messages, remove only the last one
            return currentMsgs.slice(i + 1).some((later) => later.type === 'tool_call');
          });
          useFlowStore.setState({ chatMessages: withoutToolCall });

          const resultData = event.data as Record<string, unknown>;
          if (resultData && 'proposed_diff' in resultData) {
            const diff = resultData.proposed_diff as AgentDiff;
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
      useFlowStore.getState().addChatMessage({
        id: crypto.randomUUID(),
        role: 'agent',
        content: 'Connection lost. Please try again.',
        timestamp: Date.now(),
        type: 'error',
      });
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
