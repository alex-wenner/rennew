import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useState } from "react";

import { eventsUrl } from "../api";
import type { AgentEvent, SessionMessage } from "../types";

export interface LiveTool {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "running" | "completed" | "failed";
  duration_ms?: number;
  preview?: string;
}

export interface LiveSession {
  running: boolean;
  text: string;
  reasoning: string;
  tools: LiveTool[];
  error: string | null;
  notice: string | null;
}

type LiveMap = Record<string, LiveSession>;

const empty: LiveSession = {
  running: false,
  text: "",
  reasoning: "",
  tools: [],
  error: null,
  notice: null,
};

function reduce(state: LiveMap, event: AgentEvent): LiveMap {
  const current = state[event.session_id] ?? empty;
  switch (event.type) {
    case "run.started":
      return { ...state, [event.session_id]: { ...empty, running: true } };
    case "message.delta":
      return { ...state, [event.session_id]: { ...current, text: current.text + event.delta } };
    case "reasoning.delta":
      return {
        ...state,
        [event.session_id]: { ...current, reasoning: current.reasoning + event.delta },
      };
    case "tool.started":
      return {
        ...state,
        [event.session_id]: {
          ...current,
          tools: [
            ...current.tools.filter((t) => t.id !== event.tool_call_id),
            {
              id: event.tool_call_id,
              name: event.tool,
              arguments: event.arguments,
              status: "running",
            },
          ],
        },
      };
    case "tool.finished":
      return {
        ...state,
        [event.session_id]: {
          ...current,
          tools: current.tools.map((t) =>
            t.id === event.tool_call_id
              ? {
                  ...t,
                  status: event.status === "completed" ? "completed" : "failed",
                  duration_ms: event.duration_ms,
                  preview: event.preview,
                }
              : t,
          ),
        },
      };
    case "message.saved":
      // The saved message now carries the streamed text; reset live buffers.
      return {
        ...state,
        [event.session_id]: { ...current, text: "", reasoning: "", tools: [] },
      };
    case "run.notice":
      return { ...state, [event.session_id]: { ...current, notice: event.notice } };
    case "run.error":
      return { ...state, [event.session_id]: { ...current, running: false, error: event.error } };
    case "run.finished":
      return { ...state, [event.session_id]: { ...empty, notice: current.notice } };
    default:
      return state;
  }
}

export function useAgentEvents() {
  const [state, dispatch] = useReducer(reduce, {});
  const [connection, setConnection] = useState<"connecting" | "connected" | "reconnecting">("connecting");
  const queryClient = useQueryClient();

  useEffect(() => {
    const source = new EventSource(eventsUrl);
    source.addEventListener("connected", () => {
      setConnection("connected");
      void queryClient.invalidateQueries();
    });
    source.onerror = () => setConnection("reconnecting");
    source.onmessage = (raw) => {
      let event: AgentEvent;
      try {
        event = JSON.parse(raw.data) as AgentEvent;
      } catch {
        return;
      }
      dispatch(event);
      if (event.type === "message.saved") {
        queryClient.setQueryData<SessionMessage[]>(["messages", event.session_id], (messages) => {
          if (!messages) return undefined;
          return [...messages.filter((message) => message.id !== event.message.id), event.message];
        });
        void queryClient.invalidateQueries({ queryKey: ["messages", event.session_id] });
        void queryClient.invalidateQueries({ queryKey: ["sessions"] });
      }
      if (event.type === "change.created") {
        void queryClient.invalidateQueries({ queryKey: ["changes"] });
        void queryClient.invalidateQueries({ queryKey: ["graph"] });
      }
      if (event.type === "memory.created" || event.type === "session.compacted") {
        void queryClient.invalidateQueries({ queryKey: ["memories"] });
        void queryClient.invalidateQueries({ queryKey: ["graph"] });
      }
      if (event.type === "run.finished" || event.type === "run.started" || event.type === "run.error") {
        void queryClient.invalidateQueries({ queryKey: ["sessions"] });
        void queryClient.invalidateQueries({ queryKey: ["graph"] });
        void queryClient.invalidateQueries({ queryKey: ["health"] });
        void queryClient.invalidateQueries({ queryKey: ["messages", event.session_id] });
      }
    };
    return () => source.close();
  }, [queryClient]);

  return { sessions: state, connection };
}

export const emptyLive = empty;
