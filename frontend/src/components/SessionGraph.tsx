import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";

import type { GraphSnapshot } from "../types";

interface SessionGraphProps {
  snapshot: GraphSnapshot;
  selectedId: string | null;
  onSelect: (sessionId: string) => void;
}

export function SessionGraph({ snapshot, selectedId, onSelect }: SessionGraphProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const graph = cytoscape({
      container: container.current,
      elements: [
        ...snapshot.nodes.map((node) => ({
          data: { id: node.id, label: node.label, ...node.properties },
          classes: node.id === selectedId ? "selected" : "",
        })),
        ...snapshot.edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: String(edge.properties.kind ?? edge.kind),
          },
          classes: edge.kind,
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#1b211b",
            "border-color": "#667263",
            "border-width": 1,
            color: "#e8eadf",
            label: "data(label)",
            "font-family": "ui-monospace, SFMono-Regular, Consolas, monospace",
            "font-size": 11,
            "text-margin-y": 7,
            "text-valign": "bottom",
            height: 42,
            width: 42,
          },
        },
        {
          selector: "node.selected",
          style: {
            "background-color": "#c7ff6b",
            "border-color": "#e9ffbf",
            "border-width": 3,
            color: "#c7ff6b",
          },
        },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "line-color": "#5d685b",
            "target-arrow-color": "#5d685b",
            "target-arrow-shape": "triangle",
            width: 1.5,
            label: "data(label)",
            color: "#899187",
            "font-size": "8px",
            "text-background-color": "#10120f",
            "text-background-opacity": 0.85,
            "text-background-padding": "3px",
          },
        },
        {
          selector: "edge.overlap",
          style: { "line-style": "dashed", "target-arrow-shape": "none" },
        },
        {
          selector: "edge.handoff",
          style: { "line-color": "#c7ff6b", "target-arrow-color": "#c7ff6b" },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 48,
        nodeRepulsion: () => 7000,
      },
      minZoom: 0.35,
      maxZoom: 2.5,
    });

    graph.on("tap", "node", (event) => onSelect(event.target.id()));
    return () => graph.destroy();
  }, [snapshot, selectedId, onSelect]);

  return (
    <div className="graph-stage">
      <div className="graph-grid" />
      <div className="graph-canvas" ref={container} />
      {snapshot.nodes.length === 0 ? (
        <div className="graph-empty">
          <span>SESSION GRAPH</span>
          <strong>Nothing connected yet.</strong>
          <p>Create a session. Handoffs and overlaps will collect around it.</p>
        </div>
      ) : null}
    </div>
  );
}
