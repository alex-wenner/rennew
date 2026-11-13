import { Diff, Hunk, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";

import type { FileChange } from "../types";

interface DiffViewProps {
  change: FileChange;
  compact?: boolean;
}

export function DiffView({ change, compact = false }: DiffViewProps) {
  const files = parseDiff(change.diff);
  return (
    <div className={`diff ${compact ? "diff--compact" : ""}`}>
      <div className="diff__header">
        <span className={`diff__kind diff__kind--${change.kind}`}>{change.kind}</span>
        <span className="diff__path">{change.path}</span>
        <span className="diff__stats">
          <span className="diff__add">+{change.additions}</span>
          <span className="diff__del">−{change.deletions}</span>
        </span>
      </div>
      <div className="diff__body">
        {files.map((file) => (
          <Diff
            key={`${file.oldRevision}-${file.newRevision}`}
            diffType={file.type}
            hunks={file.hunks}
            viewType="unified"
          >
            {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
          </Diff>
        ))}
        {files.length === 0 && <pre className="diff__raw">{change.diff}</pre>}
      </div>
    </div>
  );
}
