export type SessionStatus = "active" | "blocked" | "completed" | "archived";

export interface Session {
  id: string;
  title: string;
  status: SessionStatus;
  provider: string | null;
  model: string | null;
  mode: string;
  workspace: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_reasoning_tokens: number;
  total_cost_usd: number;
  created_at: string;
  updated_at: string;
}

export interface ToolCallRecord {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  status: string;
  duration_ms: number;
}

export interface TokenMetrics {
  input: number;
  output: number;
  reasoning: number;
  cache_read: number;
  cache_write: number;
  total: number;
  cost_usd: number;
}

export interface SessionMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning: string | null;
  tool_calls: ToolCallRecord[];
  tokens: TokenMetrics;
  created_at: string;
}

export interface PromptRequest {
  prompt: string;
  mode?: string;
  provider?: string;
  model?: string;
  reasoning_effort?: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  input_per_m: number | null;
  output_per_m: number | null;
  context: number | null;
  reasoning: boolean;
}

export interface ProviderInfo {
  id: string;
  label: string;
  auth: string;
  streaming: boolean;
  tool_calling: boolean;
  reasoning: boolean;
  context_window: number | null;
  models: ModelInfo[];
  api: string | null;
  connected: boolean;
  auth_source: string | null;
  auth_env: string | null;
}

export interface FileChange {
  id: string;
  session_id: string;
  message_id: string | null;
  tool_call_id: string | null;
  path: string;
  kind: "create" | "edit" | "delete";
  before_hash: string;
  after_hash: string;
  additions: number;
  deletions: number;
  diff: string;
  created_at: string;
}

export interface MemoryEntry {
  id: string;
  scope: string;
  content: string;
  source: string;
  confidence: number;
  created_at: string;
}

export interface GraphNode {
  id: string;
  kind: "session" | "change" | "memory" | "compaction" | string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: string;
  properties: Record<string, unknown>;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphQueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface McpStatus {
  name: string;
  status: string;
  command?: string;
  error?: string;
}

export interface ToolsDescription {
  workspace: string;
  builtin: { name: string; description: string }[];
  skills: { name: string; description: string; path: string }[];
  skill_roots: string[];
  mcp: { config_path: string; servers: McpStatus[]; tools: string[] };
}

export interface AuthStatus {
  status: "idle" | "pending" | "complete" | "error";
  user_code?: string;
  verification_uri?: string;
  url?: string;
  error?: string;
}

export type AgentEvent =
  | { type: "run.started"; session_id: string; provider: string; model: string; at: string }
  | { type: "message.delta"; session_id: string; delta: string; at: string }
  | { type: "reasoning.delta"; session_id: string; delta: string; at: string }
  | {
      type: "tool.started";
      session_id: string;
      tool: string;
      tool_call_id: string;
      arguments: Record<string, unknown>;
      at: string;
    }
  | {
      type: "tool.finished";
      session_id: string;
      tool: string;
      tool_call_id: string;
      status: string;
      duration_ms: number;
      preview: string;
      at: string;
    }
  | { type: "message.saved"; session_id: string; message: SessionMessage; at: string }
  | { type: "change.created"; session_id: string; change: FileChange; at: string }
  | { type: "memory.created"; session_id: string; memory: MemoryEntry; at: string }
  | { type: "session.compacted"; session_id: string; at: string }
  | { type: "run.notice"; session_id: string; notice: string; at: string }
  | { type: "run.error"; session_id: string; error: string; at: string }
  | { type: "run.finished"; session_id: string; usage: Record<string, number>; at: string };
