import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listAllChanges, listSessionChanges } from "../api";
import type { FileChange } from "../types";
import { DiffView } from "./DiffView";

interface ChangesPanelProps {
  sessionId: string | null;
}

export function ChangesPanel({ sessionId }: ChangesPanelProps) {
  const [scope, setScope] = useState<"session" | "all">("session");
  const [openId, setOpenId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["changes", scope === "session" ? sessionId : "all"],
    queryFn: () =>
      scope === "session" && sessionId ? listSessionChanges(sessionId) : listAllChanges(),
    enabled: scope === "all" || Boolean(sessionId),
  });
  const changes = query.data ?? [];
  const open = changes.find((c) => c.id === openId) ?? null;

  const totals = changes.reduce(
    (acc, c) => ({ add: acc.add + c.additions, del: acc.del + c.deletions }),
    { add: 0, del: 0 },
  );

  if (open) {
    return (
      <div className="panel">
        <div className="panel__bar">
          <button className="link" onClick={() => setOpenId(null)} type="button">
            ← All changes
          </button>
        </div>
        <div className="panel__scroll">
          <DiffView change={open} />
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__bar">
        <div className="seg">
          <button className={scope === "session" ? "on" : ""} disabled={!sessionId} onClick={() => setScope("session")} type="button">
            Session
          </button>
          <button className={scope === "all" ? "on" : ""} onClick={() => setScope("all")} type="button">
            All
          </button>
        </div>
        <span className="muted">
          {changes.length} files · <span className="diff__add">+{totals.add}</span>{" "}
          <span className="diff__del">−{totals.del}</span>
        </span>
      </div>
      <div className="panel__scroll">
        
        {changes.map((change) => (
          <ChangeRow key={change.id} change={change} onOpen={() => setOpenId(change.id)} />
        ))}
      </div>
    </div>
  );
}

function ChangeRow({ change, onOpen }: { change: FileChange; onOpen: () => void }) {
  const dir = change.path.includes("/") ? change.path.slice(0, change.path.lastIndexOf("/") + 1) : "";
  const name = change.path.slice(dir.length);
  return (
    <button className="change" onClick={onOpen} type="button">
      <span className={`diff__kind diff__kind--${change.kind}`}>{change.kind[0]}</span>
      <span className="change__path">
        <span className="muted">{dir}</span>
        {name}
      </span>
      <span className="diff__stats">
        <span className="diff__add">+{change.additions}</span>
        <span className="diff__del">−{change.deletions}</span>
      </span>
    </button>
  );
}
