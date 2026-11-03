import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { GitBranch, Info, RefreshCcw } from "lucide-react";
import { useGraph } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Select } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import { useTheme } from "@/theme/ThemeContext";

const NODE_COLORS_LIGHT: Record<string, string> = {
  evidence: "#0891b2",
  event: "#4f46e5",
  phone: "#059669",
  upi_vpa: "#db2777",
  ip: "#dc2626",
  username: "#7c3aed",
  utr: "#d97706",
  filename: "#64748b",
  transaction_id: "#ea580c",
  invoice_id: "#2563eb",
  host: "#475569",
  email: "#0d9488",
  url: "#0284c7",
  amount: "#ca8a04",
  cell_tower: "#9333ea",
  default: "#d97706",
};

const NODE_COLORS_DARK: Record<string, string> = {
  evidence: "#22d3ee",
  event: "#818cf8",
  phone: "#34d399",
  upi_vpa: "#f472b6",
  ip: "#f87171",
  username: "#a78bfa",
  utr: "#fbbf24",
  filename: "#94a3b8",
  transaction_id: "#fb923c",
  invoice_id: "#60a5fa",
  host: "#64748b",
  email: "#2dd4bf",
  url: "#38bdf8",
  amount: "#facc15",
  cell_tower: "#c084fc",
  default: "#f59e0b",
};

const GRAPH_PALETTES = {
  light: {
    label: "#334155",
    border: "#ffffff",
    edge: "#94a3b8",
    exact: "#059669",
    conflict: "#e11d48",
    heuristic: "#d97706",
  },
  dark: {
    label: "#cbd5e1",
    border: "#0f172a",
    edge: "#475569",
    exact: "#34d399",
    conflict: "#fb7185",
    heuristic: "#fbbf24",
  },
};

interface SelectedElement {
  kind: "node" | "edge";
  data: Record<string, unknown>;
}

export function GraphPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { theme } = useTheme();
  const nodeColors = theme === "dark" ? NODE_COLORS_DARK : NODE_COLORS_LIGHT;
  const palette = GRAPH_PALETTES[theme];
  const [includeTemporal, setIncludeTemporal] = useState(false);
  const [layout, setLayout] = useState("cose");
  const [showEvidence, setShowEvidence] = useState(true);
  const [showEvents, setShowEvents] = useState(true);
  const [showEntities, setShowEntities] = useState(true);
  const [selected, setSelected] = useState<SelectedElement | null>(null);
  const graphQuery = useGraph(caseId, includeTemporal);

  const nodes = useMemo(() => graphQuery.data?.nodes ?? [], [graphQuery.data]);
  const edges = useMemo(() => graphQuery.data?.edges ?? [], [graphQuery.data]);

  const visibleElements = useMemo<ElementDefinition[]>(() => {
    const allowedNodeIds = new Set(
      nodes
        .filter((node) =>
          node.node_type === "evidence"
            ? showEvidence
            : node.node_type === "event"
              ? showEvents
              : showEntities,
        )
        .map((node) => node.id),
    );
    const nodeElements = nodes
      .filter((node) => allowedNodeIds.has(node.id))
      .map((node) => ({
        data: {
          ...node.data,
          id: node.id,
          label: node.label,
          node_type: node.node_type,
          color:
            nodeColors[
              String(node.data.entity_type ?? node.node_type ?? "default")
            ] ?? nodeColors.default,
        },
      }));
    const edgeElements = edges
      .filter((edge) => allowedNodeIds.has(edge.source) && allowedNodeIds.has(edge.target))
      .map((edge) => ({
        data: {
          ...(edge.data ?? {}),
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label ?? "",
          edge_type: edge.edge_type,
          match_method: edge.match_method,
          explanation: edge.explanation,
          confidence: edge.confidence,
          line_style: edge.match_method === "heuristic" ? "dashed" : "solid",
        },
      }));
    return [...nodeElements, ...edgeElements];
  }, [nodes, edges, showEvidence, showEvents, showEntities, nodeColors]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (graphQuery.isLoading) return <LoadingState label="Building relationship graph…" />;
  if (graphQuery.error)
    return <ErrorState message={graphQuery.error.message} onRetry={() => graphQuery.refetch()} />;

  return (
    <div>
      <PageHeader
        eyebrow="Relationship graph"
        title="Evidence, events and entities"
        description="Exact identifier matches are labelled separately from heuristic leads. A temporal proximity edge is a lead, not proof of a relationship."
        actions={
          <>
            <Button
              variant={includeTemporal ? "primary" : "secondary"}
              icon={<RefreshCcw size={14} />}
              onClick={() => setIncludeTemporal((current) => !current)}
            >
              {includeTemporal ? "Temporal leads on" : "Include temporal leads"}
            </Button>
            <Select
              value={layout}
              onChange={(event) => setLayout(event.target.value)}
              className="w-40 text-xs"
            >
              <option value="cose">COSE layout</option>
              <option value="circle">Circle layout</option>
              <option value="grid">Grid layout</option>
              <option value="breadthfirst">Breadth-first</option>
            </Select>
          </>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader
            title="Graph canvas"
            subtitle={`${nodes.length} nodes · ${edges.length} edges`}
            action={
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                <Toggle label="Evidence" checked={showEvidence} onChange={setShowEvidence} />
                <Toggle label="Events" checked={showEvents} onChange={setShowEvents} />
                <Toggle label="Entities" checked={showEntities} onChange={setShowEntities} />
              </div>
            }
          />
          <CardBody className="p-0">
            {nodes.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="No graph data"
                  description="Parse evidence and run reconciliation to build relationships."
                  icon={GitBranch}
                />
              </div>
            ) : (
              <CytoscapeCanvas
                elements={visibleElements}
                layout={layout}
                onSelect={setSelected}
              />
            )}
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Legend" subtitle="Relationship and node types" />
            <CardBody className="space-y-2 text-[11px] text-muted">
              <Legend color={nodeColors.evidence} label="Evidence file" />
              <Legend color={nodeColors.event} label="Extracted event" />
              <Legend color={nodeColors.upi_vpa} label="Entity (VPA, phone, UTR, …)" />
              <div className="my-2 h-px bg-surface-2" />
              <Legend line color={palette.exact} label="Exact identifier match" />
              <Legend line color={palette.conflict} label="Conflict / discrepancy" />
              <Legend line dashed color={palette.heuristic} label="Heuristic temporal lead" />
              <Legend line color={palette.edge} label="Containment / extraction" />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Selection" subtitle="Click a node or edge" />
            <CardBody>
              {!selected ? (
                <p className="text-xs text-muted">
                  Select a node or edge to inspect its explanation and supporting records.
                </p>
              ) : (
                <div className="space-y-3">
                  <Badge className="border-accent/30 bg-accent/10 text-accent">
                    {selected.kind}
                  </Badge>
                  <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-2/60 p-3 font-mono text-[10px] leading-relaxed text-secondary">
                    {JSON.stringify(selected.data, null, 2)}
                  </pre>
                  {selected.kind === "edge" ? (
                    <div className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 p-3 text-[11px] leading-relaxed text-amber-800/80 dark:text-amber-100/80">
                      <Info size={12} className="mr-1 inline" />
                      Only exact identifier matches and deterministic conflicts are treated as
                      direct relationships. Temporal or fuzzy links are investigative leads.
                    </div>
                  ) : null}
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-1.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-3.5 w-3.5 rounded border-line-strong bg-surface text-accent"
      />
      {label}
    </label>
  );
}

function Legend({
  color,
  label,
  line,
  dashed,
}: {
  color: string;
  label: string;
  line?: boolean;
  dashed?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      {line ? (
        <span
          className={cn("h-0.5 w-6", dashed && "opacity-80")}
          style={{
            backgroundImage: dashed
              ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 8px)`
              : undefined,
            backgroundColor: dashed ? undefined : color,
          }}
        />
      ) : (
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
      )}
      <span>{label}</span>
    </div>
  );
}

function CytoscapeCanvas({
  elements,
  layout,
  onSelect,
}: {
  elements: ElementDefinition[];
  layout: string;
  onSelect: (selected: SelectedElement | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const { theme } = useTheme();
  const palette = GRAPH_PALETTES[theme];

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            color: palette.label,
            "font-size": 9,
            "text-valign": "bottom",
            "text-margin-y": 4,
            "text-wrap": "ellipsis",
            "text-max-width": "110px",
            width: 22,
            height: 22,
            "border-width": 2,
            "border-color": palette.border,
          },
        },
        {
          selector: 'node[node_type = "evidence"]',
          style: { shape: "round-rectangle", width: 34, height: 24 },
        },
        {
          selector: 'node[node_type = "entity"]',
          style: { shape: "diamond", width: 24, height: 24 },
        },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": palette.edge,
            "target-arrow-color": palette.edge,
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.8,
          },
        },
        {
          selector: 'edge[edge_type = "exact_identifier_match"], edge[edge_type = "exact_utr_match"]',
          style: {
            "line-color": palette.exact,
            "target-arrow-color": palette.exact,
            width: 2,
          },
        },
        {
          selector: 'edge[edge_type = "amount_conflict"], edge[edge_type = "payee_conflict"]',
          style: {
            "line-color": palette.conflict,
            "target-arrow-color": palette.conflict,
            width: 2.2,
          },
        },
        {
          selector: 'edge[match_method = "heuristic"]',
          style: {
            "line-color": palette.heuristic,
            "target-arrow-color": palette.heuristic,
            "line-style": "dashed",
            opacity: 0.6,
          },
        },
      ],
      layout: { name: "cose", fit: true, padding: 40 },
      minZoom: 0.2,
      maxZoom: 2.5,
    });

    cy.on("tap", "node", (event) => {
      onSelect({ kind: "node", data: event.target.data() });
    });
    cy.on("tap", "edge", (event) => {
      onSelect({ kind: "edge", data: event.target.data() });
    });
    cy.on("tap", (event) => {
      if (event.target === cy) onSelect(null);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [onSelect, theme, palette]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().remove();
    cy.add(elements);
    const layoutInstance = cy.layout({ name: layout });
    layoutInstance.run();
    layoutInstance.one("layoutstop", () => cy.fit(undefined, 40));
  }, [elements, layout]);

  return <div ref={containerRef} className="graph-canvas h-[620px] w-full" />;
}
