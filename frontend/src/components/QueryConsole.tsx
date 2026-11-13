import { sql } from "@codemirror/lang-sql";
import { useMutation } from "@tanstack/react-query";
import CodeMirror from "@uiw/react-codemirror";
import { useState } from "react";

import { queryGraph } from "../api";

const initialQuery = `MATCH (s:Session)-[:CHANGED]->(f:FileChange)
RETURN s.title AS session, f.path AS path, f.additions AS adds, f.deletions AS dels
ORDER BY f.created_at DESC LIMIT 50`;

export function QueryConsole() {
  const [query, setQuery] = useState(initialQuery);
  const run = useMutation({ mutationFn: () => queryGraph(query) });

  return (
    <div className="panel">
      <div className="cypher">
        <CodeMirror
          basicSetup={{ foldGutter: false, highlightActiveLine: false, lineNumbers: false }}
          extensions={[sql()]}
          height="140px"
          onChange={setQuery}
          theme="dark"
          value={query}
        />
      </div>
      <div className="panel__bar">
        <span className="muted">{run.data ? `${run.data.rows.length} rows` : "read-only Cypher"}</span>
        <button className="btn" disabled={run.isPending} onClick={() => run.mutate()} type="button">
          Run
        </button>
      </div>
      {run.error && <div className="error">{run.error.message}</div>}
      <div className="panel__scroll">
        {run.data && run.data.rows.length > 0 && (
          <table className="table">
            <thead>
              <tr>{run.data.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {run.data.rows.map((row, i) => (
                <tr key={i}>{run.data!.columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}</tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
