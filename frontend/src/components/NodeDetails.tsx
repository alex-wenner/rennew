import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { listAllChanges } from "../api";
import type { GraphNode } from "../types";
import { DiffView } from "./DiffView";

export function NodeDetails({
  node,
  onClose,
  onOpenSession,
}: {
  node: GraphNode;
  onClose: () => void;
  onOpenSession: (id: string) => void;
}) {
  const changesQuery = useQuery({
    queryKey: ["changes", "all"],
    queryFn: listAllChanges,
    enabled: node.kind === "change",
  });
  const change = node.kind === "change" ? changesQuery.data?.find((c) => c.id === node.id) : undefined;
  const entries = Object.entries(node.properties).filter(([k]) => !["id", "diff"].includes(k));
  const sessionId =
    node.kind === "session" ? node.id : typeof node.properties.session_id === "string" ? node.properties.session_id : null;

  return (
    <div className="node">
      <div className="node__head">
        <span className={`tag tag--${node.kind}`}>{node.kind}</span>
        <strong title={node.label}>{node.label}</strong>
        {sessionId && (
          <button className="link" onClick={() => onOpenSession(sessionId)} type="button">
            open session
          </button>
        )}
        <button className="icon" onClick={onClose} type="button">
          <X size={13} />
        </button>
      </div>
      <div className="node__body">
        {change ? (
          <DiffView change={change} compact />
        ) : (
          <dl className="node__props">
            {entries.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>
  );
}
