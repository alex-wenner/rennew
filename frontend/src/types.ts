export type SessionStatus = "active" | "blocked" | "completed" | "archived";

export interface Session {
  id: string;
  title: string;
  status: SessionStatus;
  provider: string | null;
  model: string | null;
  created_at: string;
  updated_at: string;
}

export interface GraphNode {
  id: string;
  kind: string;
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

export interface Compaction {
  id: string;
  session_id: string;
  objective: string;
  completed: string;
  active: string;
  blocked: string;
  next_move: string;
  relevant_files: string;
  tokens_saved: number;
  created_at: string;
}

