import { Maximize2, Minimize2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { GraphCanvas, type GraphEdge as RGEdge, type GraphNode as RGNode, type Theme, darkTheme } from "reagraph";

import type { GraphNode, GraphSnapshot } from "../types";
import { NodeDetails } from "./NodeDetails";

interface GraphViewProps {
  snapshot: GraphSnapshot;
  selectedSessionId: string | null;
  onSelectSession: (id: string) => void;
  fullscreen: boolean;
  onToggleFullscreen: () => void;
}

const COLORS: Record<string, string> = {
  session: "#8b9cf9",
  change: "#6fcf97",
  memory: "#f2c26b",
  compaction: "#c084fc",
  file: "#5c6270",
};

const theme: Theme = {
  ...darkTheme,
  canvas: { background: "#0e0f11", fog: "#0e0f11" },
  node: {
    ...darkTheme.node,
    fill: "#8b9cf9",
    activeFill: "#c7d0ff",
    opacity: 1,
    selectedOpacity: 1,
    inactiveOpacity: 0.2,
    label: { color: "#c9cbd1", stroke: "#0e0f11", activeColor: "#ffffff" },
  },
  edge: {
    ...darkTheme.edge,
    fill: "#2e3138",
    activeFill: "#8b9cf9",
    opacity: 0.9,
    selectedOpacity: 1,
    inactiveOpacity: 0.12,
    label: { color: "#8a8d95", stroke: "#0e0f11", activeColor: "#ffffff" },
  },
  ring: { fill: "#8b9cf9", activeFill: "#c7d0ff" },
  arrow: { fill: "#2e3138", activeFill: "#8b9cf9" },
  lasso: { border: "1px solid #8b9cf9", background: "rgba(139,156,249,0.1)" },
};

export function GraphView({
  snapshot,
  selectedSessionId,
  onSelectSession,
  fullscreen,
  onToggleFullscreen,
}: GraphViewProps) {
  const [scope, setScope] = useState<"all" | "session">("all");
  const [node, setNode] = useState<GraphNode | null>(null);
  const [layout, setLayout] = useState<"forceDirected2d" | "radialOut2d" | "hierarchicalTd">("forceDirected2d");

  const { nodes, edges } = useMemo(() => {
    let visibleNodes = snapshot.nodes;
    let visibleEdges = snapshot.edges;

    // Cross-session structure: changes to the same path are linked through a
    // shared file node, so overlapping work between sessions is visible.
    const byPath = new Map<string, string[]>();
    for (const n of visibleNodes) {
      if (n.kind === "change") {
        const path = String(n.properties.path ?? "");
        byPath.set(path, [...(byPath.get(path) ?? []), n.id]);
      }
    }
    const fileNodes: GraphNode[] = [];
    const fileEdges = [] as GraphSnapshot["edges"];
    for (const [path, ids] of byPath) {
      if (ids.length < 2) continue;
      const fid = `file:${path}`;
      fileNodes.push({ id: fid, kind: "file", label: path.split("/").pop() ?? path, properties: { path, changes: ids.length } });
      for (const id of ids) fileEdges.push({ id: `${fid}:${id}`, source: id, target: fid, kind: "file", properties: {} });
    }
    visibleNodes = [...visibleNodes, ...fileNodes];
    visibleEdges = [...visibleEdges, ...fileEdges];

    if (scope === "session" && selectedSessionId) {
      const keep = new Set<string>([selectedSessionId]);
      for (const e of visibleEdges) {
        if (e.source === selectedSessionId) keep.add(e.target);
        if (e.target === selectedSessionId) keep.add(e.source);
      }
      // second hop for file links
      for (const e of visibleEdges) if (keep.has(e.source) && e.kind === "file") keep.add(e.target);
      visibleNodes = visibleNodes.filter((n) => keep.has(n.id));
      visibleEdges = visibleEdges.filter((e) => keep.has(e.source) && keep.has(e.target));
    }

    const rgNodes: RGNode[] = visibleNodes.map((n) => ({
      id: n.id,
      label: n.label,
      fill: COLORS[n.kind] ?? "#9aa0a6",
      size:
        n.kind === "session"
          ? 7 + Math.min(5, Math.log2(2 + Number(n.properties.messages ?? 0)))
          : n.kind === "change"
            ? 3 + Math.min(3, Math.log2(2 + Number(n.properties.additions ?? 0) + Number(n.properties.deletions ?? 0)))
            : n.kind === "file"
              ? 4
              : 3,
      data: n,
    }));
    const rgEdges: RGEdge[] = visibleEdges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.kind === "handoff" || e.kind === "overlap" ? e.kind : undefined,
      size: e.kind === "handoff" ? 2 : e.kind === "file" ? 0.6 : 1,
    }));
    return { nodes: rgNodes, edges: rgEdges };
  }, [snapshot, scope, selectedSessionId]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { session: 0, change: 0, memory: 0, compaction: 0 };
    for (const n of snapshot.nodes) c[n.kind] = (c[n.kind] ?? 0) + 1;
    return c;
  }, [snapshot]);

  const canvas = (
    <div className="graph__canvas">
      {nodes.length === 0 ? (
        <div className="graph__empty" />
      ) : (
        <GraphCanvas
          animated
          draggable
          edgeArrowPosition="none"
          edges={edges}
          labelType="nodes"
          layoutType={layout}
          nodes={nodes}
          onCanvasClick={() => setNode(null)}
          onNodeClick={(n) => {
            const data = n.data as GraphNode;
            setNode(data);
            if (data.kind === "session") onSelectSession(data.id);
            else if (typeof data.properties.session_id === "string") onSelectSession(data.properties.session_id);
          }}
          selections={node ? [node.id] : []}
          theme={theme}
        />
      )}
    </div>
  );

  return (
    <div className="graph">
      <div className="graph__bar">
        <div className="legend">
          <span><i style={{ background: COLORS.session }} />{counts.session ?? 0}</span>
          <span><i style={{ background: COLORS.change }} />{counts.change ?? 0}</span>
          <span><i style={{ background: COLORS.memory }} />{counts.memory ?? 0}</span>
          <span><i style={{ background: COLORS.compaction }} />{counts.compaction ?? 0}</span>
        </div>
        <div className="graph__controls">
          <select className="pill" onChange={(e) => setLayout(e.target.value as typeof layout)} value={layout}>
            <option value="forceDirected2d">force</option>
            <option value="radialOut2d">radial</option>
            <option value="hierarchicalTd">tree</option>
          </select>
          <div className="seg">
            <button className={scope === "all" ? "on" : ""} onClick={() => setScope("all")} type="button">All</button>
            <button className={scope === "session" ? "on" : ""} disabled={!selectedSessionId} onClick={() => setScope("session")} type="button">
              Session
            </button>
          </div>
          <button className="icon" onClick={onToggleFullscreen} title={fullscreen ? "Exit fullscreen" : "Fullscreen"} type="button">
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>
      {node ? (
        <Group className="graph__split" orientation="vertical">
          <Panel defaultSize="60" minSize="20">{canvas}</Panel>
          <Separator className="handle handle--h" />
          <Panel defaultSize="40" minSize="15">
            <NodeDetails node={node} onClose={() => setNode(null)} onOpenSession={onSelectSession} />
          </Panel>
        </Group>
      ) : (
        canvas
      )}
    </div>
  );
}
