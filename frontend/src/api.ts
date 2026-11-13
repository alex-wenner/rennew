import type {
  AuthStatus,
  FileChange,
  GraphQueryResult,
  GraphSnapshot,
  MemoryEntry,
  PromptRequest,
  ProviderInfo,
  Session,
  SessionMessage,
  ToolsDescription,
} from "./types";

const apiRoot = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiRoot}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : Array.isArray(body?.detail) ? body.detail.map((item) => item.msg).join("; ") : null;
    throw new Error(detail ?? `Request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export const listSessions = () => request<Session[]>("/sessions");

export const createSession = (input: {
  title: string;
  provider?: string;
  model?: string;
  workspace?: string;
}) => request<Session>("/sessions", { method: "POST", body: JSON.stringify(input) });

export const listMessages = (sessionId: string) =>
  request<SessionMessage[]>(`/sessions/${sessionId}/messages`);

export const promptSession = (sessionId: string, body: PromptRequest) =>
  request<SessionMessage>(`/sessions/${sessionId}/prompt`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const listSessionChanges = (sessionId: string) =>
  request<FileChange[]>(`/sessions/${sessionId}/changes`);

export const listAllChanges = () => request<FileChange[]>("/runtime/changes");

export const listMemories = () => request<MemoryEntry[]>("/runtime/memories");

export const graphSnapshot = () => request<GraphSnapshot>("/graph/snapshot");

export const queryGraph = (cypher: string) =>
  request<GraphQueryResult>("/graph/query", { method: "POST", body: JSON.stringify({ cypher }) });

export const listProviders = (live = false) =>
  request<ProviderInfo[]>(`/runtime/providers${live ? "?live=true" : ""}`);

export const connectProvider = (providerId: string, apiKey: string) =>
  request<ProviderInfo>(`/runtime/providers/${providerId}/credentials`, {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });

export const disconnectProvider = (providerId: string) =>
  request<ProviderInfo>(`/runtime/providers/${providerId}/credentials`, { method: "DELETE" });

export const githubStart = () => request<AuthStatus>("/runtime/auth/github/start", { method: "POST" });
export const githubStatus = () => request<AuthStatus>("/runtime/auth/github/status");
export const openaiStart = () => request<AuthStatus>("/runtime/auth/openai/start", { method: "POST" });
export const openaiStatus = () => request<AuthStatus>("/runtime/auth/openai/status");

export const toolsDescription = () => request<ToolsDescription>("/runtime/tools");
export const addMcpServer = (body: { name: string; command: string; args?: string[]; env?: Record<string, string> }) =>
  request<unknown>("/runtime/mcp/servers", { method: "POST", body: JSON.stringify(body) });
export const removeMcpServer = (name: string) => request<unknown>(`/runtime/mcp/servers/${name}`, { method: "DELETE" });
export const reconnectMcp = () => request<unknown>("/runtime/mcp/reconnect", { method: "POST" });

export const eventsUrl = `${apiRoot}/runtime/events`;

export const runtimeHealth = () => request<{ workspace: string; running_sessions: string[]; default_provider: string | null; default_model: string | null }>("/runtime/health");
