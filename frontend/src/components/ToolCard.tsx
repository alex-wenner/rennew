import {
  Check,
  ChevronRight,
  FileEdit,
  FilePlus,
  FileSearch,
  FolderSearch,
  Loader2,
  Terminal,
  Wrench,
  X,
} from "lucide-react";
import { useState } from "react";

import type { FileChange } from "../types";
import { DiffView } from "./DiffView";

export interface ToolCardData {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "running" | "completed" | "failed";
  duration_ms?: number;
  result?: string;
}

const ICONS: Record<string, typeof Wrench> = {
  read_file: FileSearch,
  write_file: FilePlus,
  edit_file: FileEdit,
  list_files: FolderSearch,
  grep_files: FolderSearch,
  run_command: Terminal,
};

function summarize(name: string, args: Record<string, unknown>): string {
  const first = (key: string) => (args[key] != null ? String(args[key]) : "");
  switch (name) {
    case "read_file":
    case "write_file":
    case "edit_file":
      return first("path");
    case "list_files":
    case "grep_files":
      return first("pattern");
    case "run_command":
      return first("command");
    case "skill":
      return first("name");
    case "remember":
      return first("content").slice(0, 80);
    case "recall":
      return first("query");
    default: {
      const entries = Object.entries(args);
      if (entries.length === 0) return "";
      const [k, v] = entries[0]!;
      return `${k}: ${String(v).slice(0, 60)}`;
    }
  }
}

interface ToolCardProps {
  tool: ToolCardData;
  change?: FileChange;
}

export function ToolCard({ tool, change }: ToolCardProps) {
  const [open, setOpen] = useState(Boolean(change));
  const Icon = ICONS[tool.name] ?? Wrench;
  const summary = summarize(tool.name, tool.arguments);

  return (
    <div className={`tool tool--${tool.status} ${open ? "tool--open" : ""}`}>
      <button className="tool__head" onClick={() => setOpen(!open)} type="button">
        <ChevronRight className="tool__chev" size={12} />
        <Icon className="tool__icon" size={13} />
        <span className="tool__name">{tool.name}</span>
        <span className="tool__summary">{summary}</span>
        {change && (
          <span className="tool__stats">
            <span className="diff__add">+{change.additions}</span>
            <span className="diff__del">−{change.deletions}</span>
          </span>
        )}
        <span className="tool__status">
          {tool.status === "running" && <Loader2 className="spin" size={12} />}
          {tool.status === "completed" && <Check size={12} />}
          {tool.status === "failed" && <X size={12} />}
        </span>
        {tool.duration_ms != null && <span className="tool__time">{tool.duration_ms}ms</span>}
      </button>
      {open && (
        <div className="tool__body">
          {change ? (
            <DiffView change={change} compact />
          ) : (
            <>
              {Object.keys(tool.arguments).length > 0 && (
                <pre className="tool__pre">{JSON.stringify(tool.arguments, null, 2)}</pre>
              )}
              {tool.result && <pre className="tool__pre tool__pre--result">{tool.result}</pre>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
