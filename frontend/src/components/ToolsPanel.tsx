import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";

import { addMcpServer, reconnectMcp, removeMcpServer, toolsDescription } from "../api";

export function ToolsPanel() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["tools"], queryFn: toolsDescription, refetchInterval: 5000 });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["tools"] });
  const reconnect = useMutation({ mutationFn: reconnectMcp, onSuccess: refresh });
  const desc = query.data;

  return (
    <div className="panel">
      <div className="panel__bar">
        <span className="muted">{desc?.workspace}</span>
        <button className="icon" disabled={reconnect.isPending} onClick={() => reconnect.mutate()} title="Reconnect MCP" type="button">
          <RefreshCw size={13} className={reconnect.isPending ? "spin" : ""} />
        </button>
      </div>
      <div className="panel__scroll">
        <section className="tsec">
          <h4>MCP servers</h4>
          {desc?.mcp.servers.length ? (
            <ul className="mcp-list">
              {desc.mcp.servers.map((s) => (
                <McpRow key={s.name} name={s.name} onRefresh={refresh} status={s.status} />
              ))}
            </ul>
          ) : (
            <p className="muted">
              None configured. <code>{desc?.mcp.config_path}</code>
            </p>
          )}
          <AddMcpForm onRefresh={refresh} />
        </section>

        <section className="tsec">
          <h4>Skills</h4>
          {desc?.skills.length ? (
            <ul className="skill-list">
              {desc.skills.map((s) => (
                <li key={s.name}>
                  <strong>{s.name}</strong>
                  <span className="muted">{s.description}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              Add <code>SKILL.md</code> under <code>{desc?.skill_roots[0]}</code> or{" "}
              <code>.agents/skills</code>.
            </p>
          )}
        </section>

        <section className="tsec">
          <h4>Built-in tools</h4>
          <ul className="skill-list">
            {(desc?.builtin ?? []).map((t) => (
              <li key={t.name}>
                <strong>{t.name}</strong>
                <span className="muted">{t.description}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function McpRow({ name, status, onRefresh }: { name: string; status: string; onRefresh: () => Promise<void> }) {
  const remove = useMutation({ mutationFn: () => removeMcpServer(name), onSuccess: onRefresh });
  return (
    <li className={`mcp ${status === "connected" ? "mcp--on" : "mcp--err"}`}>
      <i className={`dot ${status === "connected" ? "dot--on" : ""}`} />
      <strong>{name}</strong>
      <span className="muted">{status}</span>
      <button className="icon" disabled={remove.isPending} onClick={() => remove.mutate()} type="button">
        <Trash2 size={12} />
      </button>
    </li>
  );
}

function AddMcpForm({ onRefresh }: { onRefresh: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const add = useMutation({
    mutationFn: () =>
      addMcpServer({ name, command, args: args.trim() ? args.trim().split(/\s+/) : [] }),
    onSuccess: async () => {
      setName("");
      setCommand("");
      setArgs("");
      setOpen(false);
      await onRefresh();
    },
  });
  if (!open) {
    return (
      <button className="btn btn--ghost" onClick={() => setOpen(true)} type="button">
        <Plus size={13} /> Add server
      </button>
    );
  }
  return (
    <form
      className="mcp-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && command.trim()) add.mutate();
      }}
    >
      <input onChange={(e) => setName(e.target.value)} placeholder="name" value={name} />
      <input onChange={(e) => setCommand(e.target.value)} placeholder="command (e.g. npx)" value={command} />
      <input onChange={(e) => setArgs(e.target.value)} placeholder="args (space separated)" value={args} />
      <div className="mcp-form__row">
        <button disabled={!name.trim() || !command.trim() || add.isPending} type="submit">
          Add
        </button>
        <button onClick={() => setOpen(false)} type="button">Cancel</button>
      </div>
      {add.error && <p className="error-inline">{String((add.error as Error).message)}</p>}
    </form>
  );
}
