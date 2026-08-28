import type { Session } from "../types";

interface SessionListProps {
  sessions: Session[];
  selectedId: string | null;
  onSelect: (sessionId: string) => void;
}

export function SessionList({ sessions, selectedId, onSelect }: SessionListProps) {
  if (sessions.length === 0) {
    return (
      <div className="empty-note">
        <span className="empty-note__index">00</span>
        <p>No sessions yet. Start one to establish the graph.</p>
      </div>
    );
  }

  return (
    <ol className="session-list">
      {sessions.map((session, index) => (
        <li key={session.id}>
          <button
            className={`session-row${session.id === selectedId ? " session-row--active" : ""}`}
            onClick={() => onSelect(session.id)}
            type="button"
          >
            <span className="session-row__number">{String(index + 1).padStart(2, "0")}</span>
            <span className="session-row__body">
              <strong>{session.title}</strong>
              <small>{session.provider ?? "unassigned"}</small>
            </span>
            <span className={`status-dot status-dot--${session.status}`} title={session.status} />
          </button>
        </li>
      ))}
    </ol>
  );
}
