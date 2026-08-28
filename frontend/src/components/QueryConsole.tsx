import { sql } from "@codemirror/lang-sql";
import { useMutation } from "@tanstack/react-query";
import CodeMirror from "@uiw/react-codemirror";
import { useState } from "react";

import { queryGraph } from "../api";

const initialQuery = `MATCH (s:Session)
RETURN s.id AS id, s.title AS title, s.status AS status
ORDER BY s.updated_at DESC`;

export function QueryConsole() {
  const [query, setQuery] = useState(initialQuery);
  const execution = useMutation({ mutationFn: () => queryGraph(query) });

  return (
    <section className="query-console">
      <div className="query-console__editor">
        <div className="panel-heading">
          <span>READ-ONLY CYPHER</span>
          <button onClick={() => execution.mutate()} type="button">
            {execution.isPending ? "RUNNING" : "RUN QUERY"}
          </button>
        </div>
        <CodeMirror
          value={query}
          height="230px"
          theme="dark"
          extensions={[sql()]}
          onChange={setQuery}
          basicSetup={{ foldGutter: false, highlightActiveLine: false }}
        />
        {execution.error ? <p className="query-error">{execution.error.message}</p> : null}
      </div>
      <div className="query-console__results">
        <div className="panel-heading">
          <span>RESULT</span>
          <small>{execution.data?.rows.length ?? 0} ROWS</small>
        </div>
        {execution.data && execution.data.rows.length > 0 ? (
          <div className="result-table-wrap">
            <table className="result-table">
              <thead>
                <tr>
                  {execution.data.columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {execution.data.rows.map((row, index) => (
                  <tr key={index}>
                    {execution.data.columns.map((column) => (
                      <td key={column}>{String(row[column] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="result-empty">Run a query to inspect the underlying session graph.</p>
        )}
      </div>
    </section>
  );
}
