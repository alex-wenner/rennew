import { useQuery } from "@tanstack/react-query";

import { listMemories } from "../api";

export function MemoryPanel() {
  const query = useQuery({ queryKey: ["memories"], queryFn: listMemories });
  const memories = query.data ?? [];
  return (
    <div className="panel">
      <div className="panel__bar">
        <span className="muted">{memories.length} memories</span>
      </div>
      <div className="panel__scroll">
        
        {memories.map((m) => (
          <div className="memory" key={m.id}>
            <p>{m.content}</p>
            <span className="muted">
              {m.scope} · {m.source} · {new Date(m.created_at).toLocaleDateString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
