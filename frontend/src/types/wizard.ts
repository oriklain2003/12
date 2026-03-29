/** Option card from present_options tool */
export interface WizardOption {
  id: string;
  title: string;
  description?: string;
}

/** Result data from present_options tool */
export interface WizardOptionsData {
  question: string;
  options: WizardOption[];
  multi_select: boolean;
}

/** Node in intent preview from show_intent_preview tool */
export interface IntentPreviewNode {
  cube_id: string;
  label: string;
  category?: 'data_source' | 'filter' | 'analysis' | 'aggregation' | 'output';
  key_params?: Record<string, unknown>;
}

/** Connection in intent preview */
export interface IntentPreviewConnection {
  from_cube: string;
  from_output?: string;
  to_cube: string;
  to_input?: string;
}

/** Result data from show_intent_preview tool */
export interface IntentPreviewData {
  mission_name: string;
  mission_description?: string;
  nodes: IntentPreviewNode[];
  connections: IntentPreviewConnection[];
}

/** Result from generate_workflow tool */
export interface GenerateWorkflowResult {
  status: 'created' | 'validation_failed';
  workflow_id?: string;
  workflow_name?: string;
  errors?: Array<{
    severity: string;
    message: string;
    node_id?: string;
    cube_name?: string;
    param_name?: string;
    rule: string;
  }>;
}

/** Extended ChatMessage for wizard (adds toolData for structured tool results) */
export interface WizardChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: number;
  type?: string;
  toolName?: string;
  streaming?: boolean;
  toolData?: unknown;
  /** Set on plan_verification tool_call messages after result arrives */
  verificationResult?: 'passed' | 'issues_found';
}
