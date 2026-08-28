import type { Session } from "../types";

interface SessionInspectorProps {
  session: Session | null;
}

export function SessionInspector({ session }: SessionInspectorProps) {
  return (
    <aside className="inspector">
      <div className="panel-heading">
        <span>INSPECTOR</span>
        <small>{session ? session.id.slice(0, 10) : "NO SELECTION"}</small>
      </div>
      {session ? (
        <div className="inspector__body">
          <p className="eyebrow">SESSION</p>
          <h2>{session.title}</h2>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{session.status}</dd>
            </div>
            <div>
              <dt>Provider</dt>
              <dd>{session.provider ?? "Not assigned"}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{session.model ?? "Not assigned"}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{new Date(session.updated_at).toLocaleString()}</dd>
            </div>
          </dl>
          <div className="inspector__actions">
            <button type="button">Request review</button>
            <button type="button">Create handoff</button>
          </div>
        </div>
      ) : (
        <p className="inspector__placeholder">
          Select a session to inspect its graph neighborhood, provider, and activity.
        </p>
      )}
    </aside>
  );
}
