import { useQuery } from "@tanstack/react-query";
import { Activity, Brain, FileDiff, FolderOpen, KeyRound, Network, PanelLeft, PanelRightClose, PanelRightOpen, Terminal, Wrench } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";

import { graphSnapshot, listSessions, runtimeHealth } from "./api";
import { ChangesPanel } from "./components/ChangesPanel";
import { Conversation } from "./components/Conversation";
import { MemoryPanel } from "./components/MemoryPanel";
import { ProviderPanel } from "./components/ProviderPanel";
import { SessionRail } from "./components/SessionRail";
import { ToolsPanel } from "./components/ToolsPanel";
import { emptyLive, useAgentEvents } from "./hooks/useAgentEvents";

const GraphView = lazy(() => import("./components/GraphView").then((m) => ({ default: m.GraphView })));
const QueryConsole = lazy(() => import("./components/QueryConsole").then((m) => ({ default: m.QueryConsole })));
type Tab = "graph" | "changes" | "memory" | "tools" | "providers" | "query";
const TABS: { id: Tab; label: string; icon: typeof Network }[] = [
  { id: "graph", label: "Graph", icon: Network },
  { id: "changes", label: "Changes", icon: FileDiff },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "providers", label: "Providers", icon: KeyRound },
  { id: "query", label: "Query", icon: Terminal },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("graph");
  const [observer, setObserver] = useState(() => new URLSearchParams(location.search).get("mode") === "observer");
  const [fullscreen, setFullscreen] = useState(false);
  const [sidebar, setSidebar] = useState(() => window.innerWidth > 900);
  const [inspect, setInspect] = useState(true);
  const [mobileView, setMobileView] = useState<"chat" | "inspect">("chat");
  const [selectedId, setSelectedId] = useState<string | null | undefined>(() => new URLSearchParams(location.search).get("session") ?? undefined);
  const { sessions: live, connection } = useAgentEvents();
  const sessionsQuery = useQuery({ queryKey: ["sessions"], queryFn: listSessions });
  const graphQuery = useQuery({ queryKey: ["graph"], queryFn: graphSnapshot });
  const health = useQuery({ queryKey: ["health"], queryFn: runtimeHealth, refetchInterval: 10000 });
  const sessions = sessionsQuery.data ?? [];
  const selected = sessions.find((s) => s.id === selectedId) ?? null;
  const running = useMemo(() => {
    const ids = new Set(health.data?.running_sessions ?? []);
    for (const [id, value] of Object.entries(live)) {
      if (value.running) ids.add(id); else ids.delete(id);
    }
    return ids;
  }, [live, health.data]);
  const workspace = selected?.workspace || health.data?.workspace;

  useEffect(() => {
    if (selectedId === undefined && sessionsQuery.data) setSelectedId(sessions[0]?.id ?? null);
  }, [selectedId, sessionsQuery.data, sessions]);
  useEffect(() => {
    const url = new URL(location.href);
    if (selectedId) url.searchParams.set("session", selectedId); else url.searchParams.delete("session");
    if (observer) url.searchParams.set("mode", "observer"); else url.searchParams.delete("mode");
    history.replaceState(null, "", url);
  }, [selectedId, observer]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openProviders = () => { setTab("providers"); setInspect(true); setMobileView("inspect"); };
  const inspector = (
    <section className="inspector" aria-label="Workspace inspector">
      <nav className="inspector__tabs" aria-label="Inspector views">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button aria-pressed={tab === id} className={tab === id ? "on" : ""} key={id} onClick={() => setTab(id)} title={label} type="button">
            <Icon size={15} /><span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="inspector__content">
        <Suspense fallback={<div className="panel__empty">Loading {tab}…</div>}>
          {tab === "graph" && (graphQuery.error ? <div role="alert" className="error">{graphQuery.error.message}</div> : <GraphView fullscreen={fullscreen} onSelectSession={setSelectedId} onToggleFullscreen={() => setFullscreen((value) => !value)} selectedSessionId={selectedId ?? null} snapshot={graphQuery.data ?? { nodes: [], edges: [] }} />)}
          {tab === "changes" && <ChangesPanel sessionId={selectedId ?? null} />}
          {tab === "memory" && <MemoryPanel />}
          {tab === "tools" && <ToolsPanel />}
          {tab === "providers" && <ProviderPanel />}
          {tab === "query" && <QueryConsole />}
        </Suspense>
      </div>
    </section>
  );
  const conversation = <Conversation live={selectedId ? { ...(live[selectedId] ?? emptyLive), running: running.has(selectedId) } : emptyLive} onOpenProviders={openProviders} onSessionCreated={(session) => setSelectedId(session.id)} session={selected} defaultWorkspace={health.data?.workspace ?? ""} />;

  return (
    <div className={`app ${sidebar ? "app--sidebar" : ""} ${observer || fullscreen ? "app--observe" : ""} app--mobile-${mobileView}`}>
      <header className="top">
        <div className="top__brand">
          <button className="icon" aria-label="Toggle sessions" aria-expanded={sidebar} onClick={() => setSidebar(!sidebar)}><PanelLeft size={17} /></button>
          <span className="wordmark"><span className="brand-mark">r</span>rennew<span className="wordmark__dot">.</span></span>
        </div>
        <div className="top__workspace" title={workspace}><FolderOpen size={14} /><span>{workspace?.split(/[\\/]/).filter(Boolean).pop() || "Your workspace"}</span><span className="badge">LOCAL</span></div>
        <div className="top__right">
          <div className="seg mode-switch" aria-label="Workspace mode">
            <button className={!observer ? "on" : ""} aria-pressed={!observer} onClick={() => { setObserver(false); setFullscreen(false); }}>Workspace</button>
            <button className={observer ? "on" : ""} aria-pressed={observer} onClick={() => { setObserver(true); setTab("graph"); }}><Activity size={13} /> Observe</button>
          </div>
          <button className="icon desktop-only" aria-label={inspect ? "Hide inspector" : "Show inspector"} onClick={() => setInspect(!inspect)}>{inspect ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}</button>
        </div>
      </header>
      <div className="workspace-body">
        {sidebar && <SessionRail sessions={sessions} selectedId={selectedId ?? null} runningIds={running} onSelect={(id) => { setSelectedId(id); if (window.innerWidth < 900) setSidebar(false); }} onNew={() => { setSelectedId(null); setObserver(false); setFullscreen(false); setMobileView("chat"); if (window.innerWidth < 900) setSidebar(false); }} onOpenProviders={openProviders} loading={sessionsQuery.isPending} error={sessionsQuery.error?.message} />}
        <main className="workspace-main">
          {!observer && !fullscreen && <nav className="mobile-switch" aria-label="Workspace panels"><button className={mobileView === "chat" ? "on" : ""} onClick={() => setMobileView("chat")}>Conversation</button><button className={mobileView === "inspect" ? "on" : ""} onClick={() => { setMobileView("inspect"); setInspect(true); }}>Inspector</button></nav>}
          {observer || fullscreen ? <div className="observer-content">{observer && <div className="observer-banner"><Activity size={15} /><span><strong>Live observer</strong> Follow CLI sessions, tool activity, and graph memory.</span><code>ren chat</code></div>}{inspector}</div> : <Group className="body" orientation="horizontal"><Panel className="conversation-panel" defaultSize="58%" minSize="30%">{conversation}</Panel>{inspect && <><Separator className="handle" /><Panel className="inspector-panel" defaultSize="42%" minSize="28%">{inspector}</Panel></>}</Group>}
        </main>
      </div>
      <footer className="statusbar">
        <span><i className={`dot ${connection === "connected" ? "dot--on" : ""}`} />{connection === "connected" ? "Runtime connected" : connection === "connecting" ? "Connecting to runtime…" : "Reconnecting…"}</span>
        <span className="statusbar__workspace" title={workspace}>{workspace ?? "Loading workspace…"}</span>
        <span>{running.size ? `${running.size} running` : "Ready"}<span className="statusbar__divider">/</span>{graphQuery.data?.nodes.length ?? 0} graph nodes</span>
      </footer>
    </div>
  );
}
