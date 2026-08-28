import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { graphSnapshot, listSessions } from "./api";
import { NewSessionForm } from "./components/NewSessionForm";
import { QueryConsole } from "./components/QueryConsole";
import { SessionGraph } from "./components/SessionGraph";
import { SessionInspector } from "./components/SessionInspector";
import { SessionList } from "./components/SessionList";

type Surface = "map" | "query";

export default function App() {
  const [surface, setSurface] = useState<Surface>("map");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sessionsQuery = useQuery({ queryKey: ["sessions"], queryFn: listSessions });
  const graphQuery = useQuery({ queryKey: ["graph"], queryFn: graphSnapshot });
  const sessions = sessionsQuery.data ?? [];
  const snapshot = graphQuery.data ?? { nodes: [], edges: [] };
  const selectedSession = sessions.find((session) => session.id === selectedId) ?? null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">R</span>
          <div>
            <strong>RENNEW</strong>
            <small>LOCAL AGENT RUNTIME</small>
          </div>
        </div>
        <nav aria-label="Primary">
          <button
            className={surface === "map" ? "active" : ""}
            onClick={() => setSurface("map")}
            type="button"
          >
            SESSION MAP
          </button>
          <button
            className={surface === "query" ? "active" : ""}
            onClick={() => setSurface("query")}
            type="button"
          >
            GRAPH QUERY
          </button>
        </nav>
        <div className="runtime-state"><span /> LOCAL</div>
      </header>

      <div className="workspace">
        <aside className="session-rail">
          <div className="panel-heading">
            <span>SESSIONS</span>
            <small>{sessions.length.toString().padStart(2, "0")}</small>
          </div>
          <SessionList sessions={sessions} selectedId={selectedId} onSelect={setSelectedId} />
          <NewSessionForm />
        </aside>

        <main className="main-surface">
          {surface === "map" ? (
            <SessionGraph snapshot={snapshot} selectedId={selectedId} onSelect={setSelectedId} />
          ) : (
            <QueryConsole />
          )}
        </main>

        <SessionInspector session={selectedSession} />
      </div>

      <footer className="statusbar">
        <span>GRAPH {snapshot.nodes.length}N / {snapshot.edges.length}E</span>
        <span>READ-WRITE OWNER: RENNEW</span>
        <span>v0.1.0</span>
      </footer>
    </div>
  );
}
