/** Agent mode for the Canvas Agent chat panel */
export type AgentMode = 'optimize' | 'fix' | 'general';

/** A single chat message in the agent conversation */
export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: number;
  /** For agent messages: 'text' | 'tool_call' | 'auto_fix_prompt' | 'error' */
  type?: string;
  /** For tool_call messages: which tool is being called */
  toolName?: string;
  /** If this message contains a diff proposal */
  diff?: AgentDiff;
  /** Whether this message is still being streamed */
  streaming?: boolean;
}

/** Structured diff proposed by the Canvas Agent */
export interface AgentDiff {
  summary?: string;
  add_nodes?: Array<{
    id?: string;
    cube_id: string;
    position: { x: number; y: number };
    params?: Record<string, unknown>;
    label?: string;
  }>;
  remove_node_ids?: string[];
  update_params?: Array<{
    node_id: string;
    params: Record<string, unknown>;
  }>;
  add_edges?: Array<{
    id?: string;
    source: string;
    target: string;
    source_handle?: string;
    target_handle?: string;
  }>;
  remove_edge_ids?: string[];
}

/** SSE event from agent chat endpoint */
export interface AgentSSEEvent {
  type: 'text' | 'tool_call' | 'tool_result' | 'thinking' | 'done' | 'session';
  data: string | Record<string, unknown> | null;
}
