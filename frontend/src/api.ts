import type { GraphQueryResult, GraphSnapshot, Session } from "./types";

const apiRoot = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiRoot}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export function listSessions(): Promise<Session[]> {
  return request("/sessions");
}

export function createSession(input: {
  title: string;
  provider?: string;
  model?: string;
}): Promise<Session> {
  return request("/sessions", { method: "POST", body: JSON.stringify(input) });
}

export function graphSnapshot(): Promise<GraphSnapshot> {
  return request("/graph/snapshot");
}

export function queryGraph(cypher: string): Promise<GraphQueryResult> {
  return request("/graph/query", { method: "POST", body: JSON.stringify({ cypher }) });
}
