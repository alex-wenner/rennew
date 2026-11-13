import { ArrowUpRight, KeyRound, MessageSquare, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { Session } from "../types";

interface SessionRailProps {
  sessions: Session[];
  selectedId: string | null;
  runningIds: Set<string>;
  onSelect: (id: string) => void;
  onNew: () => void;
  onOpenProviders: () => void;
  loading: boolean;
  error?: string;
}

export function SessionRail({ sessions, selectedId, runningIds, onSelect, onNew, onOpenProviders, loading, error }: SessionRailProps) {
  const [search, setSearch] = useState("");
  const filtered = sessions.filter((session) => `${session.title} ${session.workspace ?? ""}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <aside className="rail" aria-label="Sessions">
      <div className="rail__intro"><span className="eyebrow">YOUR WORKSPACE</span><button className="rail__new-button" onClick={onNew}><Plus size={16} />New session<ArrowUpRight size={14} /></button></div>
      <label className="rail__search"><Search size={14} /><input aria-label="Search sessions" placeholder="Search sessions…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
      <div className="rail__head"><span>Recent sessions</span><span>{sessions.length}</span></div>
      <div className="rail__list">
        {loading && <p className="rail__empty">Loading sessions…</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {!loading && !error && !filtered.length && <div className="rail__empty"><MessageSquare size={20} /><p>{search ? "No matching sessions." : "A fresh start."}</p>{!search && <span>Your conversations will appear here.</span>}</div>}
        {filtered.map((session) => <button aria-current={session.id === selectedId ? "page" : undefined} className={`rail__item ${session.id === selectedId ? "on" : ""}`} key={session.id} onClick={() => onSelect(session.id)}>
          <span className="rail__title"><MessageSquare size={14} /><span>{session.title}</span>{runningIds.has(session.id) && <i className="dot dot--live" />}</span>
          <span className="rail__meta"><span>{session.workspace?.split(/[\\/]/).filter(Boolean).pop() || session.provider || "Session"}</span><time dateTime={session.updated_at}>{new Date(session.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time></span>
        </button>)}
      </div>
      <div className="rail__footer"><button onClick={onOpenProviders}><KeyRound size={15} />Providers & connections<ArrowUpRight size={13} /></button><p>Renewed workflows.<br /><span>Simple. Graph first.</span></p></div>
    </aside>
  );
}
