import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import {
  ArrowRight,
  GitBranch,
  Info,
  RotateCcw,
  Search,
  Waypoints,
} from "lucide-react";
import { useEntityDetail, useEvidence, useGraph } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input, Select } from "@/components/ui/Field";
import { SegmentedControl } from "@/components/ui/Primitives";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { formatDateTime, humanize } from "@/lib/format";
import { useTheme } from "@/theme/ThemeContext";
import type { GraphEdge, GraphNode } from "@/types";

const NODE_COLORS_LIGHT: Record<string, string> = {
  evidence: "#0891b2",
  event: "#4f46e5",
  phone: "#059669",
  person: "#0f766e",
  device: "#0369a1",
  ip: "#dc2626",
  username: "#7c3aed",
  account: "#7c3aed",
  session: "#7c3aed",
  transaction: "#ea580c",
  transaction_id: "#ea580c",
  upi_vpa: "#db2777",
  email: "#0d9488",
  filename: "#64748b",
  file: "#64748b",
  host: "#475569",
  url: "#0284c7",
  amount: "#ca8a04",
  cell_tower: "#9333ea",
  utr: "#d97706",
  invoice_id: "#2563eb",
  default: "#d97706",
};

const NODE_COLORS_DARK: Record<string, string> = {
  evidence: "#22d3ee",
  event: "#818cf8",
  phone: "#34d399",
  person: "#2dd4bf",
  device: "#38bdf8",
  ip: "#f87171",
  username: "#a78bfa",
  account: "#a78bfa",
  session: "#c4b5fd",
  transaction: "#fb923c",
  transaction_id: "#fb923c",
  upi_vpa: "#f472b6",
  email: "#5eead4",
  filename: "#94a3b8",
  file: "#94a3b8",
  host: "#64748b",
  url: "#7dd3fc",
  amount: "#facc15",
  cell_tower: "#c084fc",
  utr: "#fbbf24",
  invoice_id: "#60a5fa",
  default: "#f59e0b",
};


/**
 * Node icons.
 *
 * Cytoscape can only paint images, so each icon is an inline SVG data URI.
 * White strokes read on every category colour, and the same glyphs are reused
 * in the legend and the connections list.
 */
function svgIcon(path: string, size = 16): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="white" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const ICON_PATHS: Record<string, string> = {
  person: '<circle cx="12" cy="8" r="3.2"/><path d="M5 20c0-3.4 3.1-5.4 7-5.4s7 2 7 5.4"/>',
  phone: '<path d="M7 3h3l2 5-2.5 1.5a12 12 0 0 0 5 5L16 12l5 2v3a2 2 0 0 1-2.2 2A17 17 0 0 1 4 6.2 2 2 0 0 1 6 4z"/>',
  device: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8"/><path d="M12 16v4"/>',
  ip: '<circle cx="12" cy="12" r="8"/><path d="M4 12h16"/><path d="M12 4c2.5 2.2 3.6 5 3.6 8s-1.1 5.8-3.6 8c-2.5-2.2-3.6-5-3.6-8S9.5 6.2 12 4z"/>',
  account: '<circle cx="12" cy="8" r="3"/><path d="M5.5 20c0-3.2 2.9-5 6.5-5s6.5 1.8 6.5 5"/>',
  transaction: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h3"/>',
  money: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/>',
  email: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 6.5 8.5 6 8.5-6"/>',
  location: '<path d="M12 21s6.5-5.6 6.5-10.4A6.5 6.5 0 0 0 5.5 10.6C5.5 15.4 12 21 12 21z"/><circle cx="12" cy="10.4" r="2.3"/>',
  evidence: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  event: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4.2l2.6 1.6"/>',
  tower: '<path d="M12 4v16"/><path d="M8 7 12 4l4 3"/><path d="M6 20h12"/>',
  default: '<circle cx="12" cy="12" r="4"/>',
};

const CATEGORY_ICONS: Record<string, string> = {
  person: "person",
  phone: "phone",
  device: "device",
  ip: "ip",
  username: "account",
  account: "account",
  session: "account",
  transaction: "transaction",
  transaction_id: "transaction",
  upi_vpa: "money",
  amount: "money",
  email: "email",
  person_email: "email",
  location: "location",
  cell_tower: "tower",
  evidence: "evidence",
  file: "evidence",
  filename: "evidence",
  event: "event",
};

function iconFor(category: string): string {
  return svgIcon(ICON_PATHS[CATEGORY_ICONS[category] ?? "default"]);
}

const NODE_LABELS: Record<string, string> = {
  evidence: "Evidence file",
  event: "Extracted event",
  phone: "Phone number",
  person: "Person / contact",
  device: "Device",
  ip: "IP address",
  username: "User account",
  session: "Session",
  transaction: "Transaction",
  transaction_id: "Transaction ID",
  upi_vpa: "UPI VPA",
  email: "Email address",
  filename: "File name",
  file: "File",
  host: "Host",
  url: "URL",
  amount: "Amount",
  cell_tower: "Cell tower",
  utr: "UTR",
  invoice_id: "Invoice ID",
};

/** Cytoscape shape per entity category, so types are distinguishable without colour alone. */
const NODE_SHAPES: Record<string, string> = {
  evidence: "round-rectangle",
  event: "ellipse",
  phone: "circle",
  person: "ellipse",
  device: "round-rectangle",
  ip: "hexagon",
  username: "triangle",
  session: "pentagon",
  transaction: "octagon",
  transaction_id: "octagon",
  upi_vpa: "diamond",
  email: "ellipse",
  filename: "tag",
  file: "tag",
  cell_tower: "triangle",
  amount: "round-rectangle",
};

const GRAPH_PALETTES = {
  light: {
    label: "#3b4553",
    labelBg: "#ffffff",
    border: "#ffffff",
    nodeBorder: "#ffffff",
    edge: "#a8b0bd",
    edgeLabel: "#55606f",
    edgeLabelBg: "#ffffff",
    exact: "#14855f",
    conflict: "#d93645",
    heuristic: "#b7791f",
    selection: "#c4283a",
  },
  dark: {
    label: "#c7cdd6",
    labelBg: "#0b0e14",
    border: "#0b0e14",
    nodeBorder: "#0b0e14",
    edge: "#3b4658",
    edgeLabel: "#9ca3af",
    edgeLabelBg: "#11151d",
    exact: "#3ecf9a",
    conflict: "#f06470",
    heuristic: "#e3bb5a",
    selection: "#f06470",
  },
};

interface SelectedElement {
  kind: "node" | "edge";
  data: Record<string, unknown>;
}

type GraphMode = "simple" | "advanced";

function nodeCategory(node: GraphNode): string {
  if (node.node_type === "entity") {
    return String(node.data.entity_type ?? "entity");
  }
  return node.node_type;
}

function edgeIsContainment(edge: GraphEdge): boolean {
  return (
    edge.edge_type === "evidence_contains_event" ||
    edge.edge_type.startsWith("event_mentions_")
  );
}

export function GraphPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { theme } = useTheme();
  const nodeColors = theme === "dark" ? NODE_COLORS_DARK : NODE_COLORS_LIGHT;
  const palette = GRAPH_PALETTES[theme];
  const [searchParams] = useSearchParams();
  const focusType = searchParams.get("focusType");
  const focusId = searchParams.get("focusId");

  const [mode, setMode] = useState<GraphMode>("simple");
  const [includeTemporal, setIncludeTemporal] = useState(false);
  const [layout, setLayout] = useState("cose");
  const [showEvidence, setShowEvidence] = useState(true);
  const [showEvents, setShowEvents] = useState(true);
  const [showEntities, setShowEntities] = useState(true);
  const [evidenceFilter, setEvidenceFilter] = useState("all");
  const [reviewFilter, setReviewFilter] = useState("all");
  const [showConnections, setShowConnections] = useState(true);
  const [selected, setSelected] = useState<SelectedElement | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [search, setSearch] = useState(focusId ?? "");
  const [neighbourFocus, setNeighbourFocus] = useState(false);
  const graphQuery = useGraph(caseId, includeTemporal);
  const evidenceQuery = useEvidence(caseId);

  useEffect(() => {
    if (focusId) setSearch(focusId);
  }, [focusId]);

  const nodes = useMemo(() => graphQuery.data?.nodes ?? [], [graphQuery.data]);
  const edges = useMemo(() => graphQuery.data?.edges ?? [], [graphQuery.data]);
  const evidenceNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of evidenceQuery.data ?? []) map.set(item.id, item.original_filename);
    return map;
  }, [evidenceQuery.data]);

  const relationshipEdges = useMemo(
    () => edges.filter((edge) => !edgeIsContainment(edge)),
    [edges],
  );

  const importantEntityIds = useMemo(() => {
    const ids = new Set<string>();
    for (const edge of relationshipEdges) {
      if (edge.source.startsWith("entity:")) ids.add(edge.source);
      if (edge.target.startsWith("entity:")) ids.add(edge.target);
    }
    return ids;
  }, [relationshipEdges]);

  const visibleElements = useMemo<ElementDefinition[]>(() => {
    const searchTerm = search.trim().toLowerCase();
    const simple = mode === "simple";

    let allowedNodeIds = new Set(
      nodes
        .filter((node) => {
          const category = nodeCategory(node);
          if (category === "evidence") return !simple && showEvidence;
          if (category === "event") return !simple && showEvents;
          if (!showEntities) return false;
          if (simple && importantEntityIds.size > 0) {
            return importantEntityIds.has(node.id);
          }
          return true;
        })
        .map((node) => node.id),
    );

    if (searchTerm) {
      const matching = new Set(
        nodes
          .filter((node) =>
            `${node.id} ${node.label} ${JSON.stringify(node.data)}`
              .toLowerCase()
              .includes(searchTerm),
          )
          .map((node) => node.id),
      );
      const withContext = new Set(matching);
      for (const edge of edges) {
        if (matching.has(edge.source)) withContext.add(edge.target);
        if (matching.has(edge.target)) withContext.add(edge.source);
      }
      allowedNodeIds = new Set([...allowedNodeIds].filter((id) => withContext.has(id)));
    }

    if (neighbourFocus && selected?.kind === "node") {
      const selectedId = String(selected.data.id);
      const neighbours = new Set<string>([selectedId]);
      for (const edge of edges) {
        if (edge.source === selectedId) neighbours.add(edge.target);
        if (edge.target === selectedId) neighbours.add(edge.source);
      }
      allowedNodeIds = new Set([...allowedNodeIds].filter((id) => neighbours.has(id)));
    }

    const nodeElements = nodes
      .filter((node) => allowedNodeIds.has(node.id))
      .map((node) => {
        const category = nodeCategory(node);
        return {
          data: {
            ...node.data,
            id: node.id,
            label: node.label,
            node_type: node.node_type,
            category,
            shape: NODE_SHAPES[category] ?? "ellipse",
            color: nodeColors[category] ?? nodeColors.default,
            icon: iconFor(category),
            type_label: NODE_LABELS[category] ?? humanize(category),
          },
        };
      });

    const edgeElements = edges
      .filter((edge) => allowedNodeIds.has(edge.source) && allowedNodeIds.has(edge.target))
      .filter((edge) => (simple ? !edgeIsContainment(edge) : showConnections || edgeIsContainment(edge)))
      .filter((edge) => {
        if (evidenceFilter === "all") return true;
        return edge.supporting_evidence_ids.includes(evidenceFilter);
      })
      .filter((edge) => {
        if (reviewFilter === "all") return true;
        if (reviewFilter === "unreviewed") {
          return !edge.review_status || edge.review_status === "unreviewed";
        }
        return edge.review_status === reviewFilter;
      })
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
          relationship_id: edge.relationship_id ?? undefined,
          relationship_type: edge.relationship_type ?? undefined,
          correlation_rule: edge.correlation_rule ?? undefined,
          classification: edge.classification ?? undefined,
          review_status: edge.review_status ?? undefined,
          has_relationship: Boolean(edge.relationship_id),
          line_style: edge.match_method === "heuristic" ? "dashed" : "solid",
        },
      }));

    return [...nodeElements, ...edgeElements];
  }, [
    nodes,
    edges,
    mode,
    showEvidence,
    showEvents,
    showEntities,
    showConnections,
    evidenceFilter,
    reviewFilter,
    importantEntityIds,
    nodeColors,
    search,
    neighbourFocus,
    selected,
  ]);

  const visibleCounts = useMemo(() => {
    let nodeCount = 0;
    let edgeCount = 0;
    for (const element of visibleElements) {
      if ("source" in element.data) edgeCount += 1;
      else nodeCount += 1;
    }
    return { nodeCount, edgeCount };
  }, [visibleElements]);

  const resetView = () => {
    setSearch("");
    setEvidenceFilter("all");
    setReviewFilter("all");
    setShowEvidence(true);
    setShowEvents(true);
    setShowEntities(true);
    setShowConnections(true);
    setNeighbourFocus(false);
    setSelected(null);
    setMode("simple");
    setIncludeTemporal(false);
  };

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (graphQuery.isLoading) return <LoadingState label="Building relationship graph…" />;
  if (graphQuery.error)
    return <ErrorState message={graphQuery.error.message} onRetry={() => graphQuery.refetch()} />;

  const simple = mode === "simple";

  return (
    <div>
      <PageHeader
        eyebrow="Relationship graph"
        title="How the evidence connects"
        description="Each line explains a documented connection. Colours and shapes identify the type of entity; heuristics are drawn dashed and are leads, not proof."
        actions={
          <>
            <div data-tour="graph-mode">
            <SegmentedControl
              label="Graph mode"
              value={mode}
              onChange={setMode}
              options={[
                { value: "simple", label: "Simple" },
                { value: "advanced", label: "Advanced" },
              ]}
            />
            </div>
            <div className="relative">
              <Search
                size={13}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted"
              />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search an entity, phone, device…"
                className="w-56 pl-8 text-xs"
                aria-label="Search graph"
              />
            </div>
            <Button variant="secondary" icon={<RotateCcw size={14} />} onClick={resetView}>
              Reset view
            </Button>
          </>
        }
      />

      {simple ? (
        <div className="mb-4 rounded-xl border border-accent/20 bg-accent/5 px-4 py-3 text-xs leading-relaxed text-secondary">
          <span className="font-semibold text-accent">Simple mode: </span>
          {importantEntityIds.size > 0
            ? `Showing ${importantEntityIds.size} entities that have a documented connection, and only those connections. Switch to Advanced to see raw events and evidence files.`
            : "No documented entity-to-entity connections yet. Parse evidence or enable temporal leads to find candidates."}
        </div>
      ) : null}

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="min-w-0">
          <CardHeader
            title="Graph canvas"
            subtitle={`${visibleCounts.nodeCount} of ${nodes.filter((node) => {
              const category = nodeCategory(node);
              return category !== "evidence" && category !== "event";
            }).length || nodes.length} nodes · ${visibleCounts.edgeCount} of ${edges.length} connections shown`}
            action={
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                {!simple ? (
                  <>
                    <Toggle label="Evidence" checked={showEvidence} onChange={setShowEvidence} />
                    <Toggle label="Events" checked={showEvents} onChange={setShowEvents} />
                  </>
                ) : null}
                <Toggle label="Entities" checked={showEntities} onChange={setShowEntities} />
                {!simple ? (
                  <Toggle
                    label="Raw edges"
                    checked={showConnections}
                    onChange={setShowConnections}
                  />
                ) : null}
                <Select
                  value={layout}
                  onChange={(event) => setLayout(event.target.value)}
                  className="w-32 text-xs"
                  aria-label="Graph layout"
                >
                  <option value="cose">COSE</option>
                  <option value="circle">Circle</option>
                  <option value="grid">Grid</option>
                  <option value="breadthfirst">Breadth-first</option>
                </Select>
              </div>
            }
          />
          <CardBody className="p-0" data-tour="graph-canvas">
            {visibleElements.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="Nothing matches these filters"
                  description="Reset the view, or switch to Advanced mode to see raw events and evidence."
                  icon={GitBranch}
                  action={
                    <Button size="sm" variant="secondary" onClick={resetView}>
                      Reset view
                    </Button>
                  }
                />
              </div>
            ) : (
              <CytoscapeCanvas
                elements={visibleElements}
                layout={layout}
                mode={mode}
                onSelect={setSelected}
                onHover={setHover}
              />
            )}
            {hover ? (
              <div className="border-t border-line bg-surface-2/60 px-4 py-2 text-[11px] leading-relaxed text-secondary">
                {hover}
              </div>
            ) : null}
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card data-tour="graph-filters">
            <CardHeader title="Filters" subtitle="Narrow the graph to what matters" />
            <CardBody className="space-y-3 text-[11px] text-muted">
              <label className="block">
                <span className="mb-1 block font-semibold uppercase tracking-wider">
                  Evidence source
                </span>
                <Select
                  value={evidenceFilter}
                  onChange={(event) => setEvidenceFilter(event.target.value)}
                  className="w-full text-xs"
                >
                  <option value="all">All sources</option>
                  {(evidenceQuery.data ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.original_filename}
                    </option>
                  ))}
                </Select>
              </label>
              <label className="block">
                <span className="mb-1 block font-semibold uppercase tracking-wider">
                  Review status
                </span>
                <Select
                  value={reviewFilter}
                  onChange={(event) => setReviewFilter(event.target.value)}
                  className="w-full text-xs"
                >
                  <option value="all">All connections</option>
                  <option value="unreviewed">Unreviewed</option>
                  <option value="accepted">Accepted</option>
                  <option value="needs_review">Needs review</option>
                  <option value="rejected">Rejected</option>
                </Select>
              </label>
              <Button
                variant={includeTemporal ? "primary" : "secondary"}
                icon={<Waypoints size={14} />}
                onClick={() => setIncludeTemporal((current) => !current)}
                className="w-full"
              >
                {includeTemporal ? "Temporal leads on" : "Include temporal leads"}
              </Button>
              {includeTemporal ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50/80 p-2 leading-relaxed text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80">
                  Temporal proximity is shown dashed. Two things happening close
                  together is a lead, never proof of a connection.
                </p>
              ) : null}
            </CardBody>
          </Card>

          <Card data-tour="graph-connections-list">
            <CardHeader
              title="Connections list"
              subtitle="Keyboard-accessible alternative to the canvas"
            />
            <CardBody>
              <ul className="max-h-56 space-y-1 overflow-auto pr-1 text-[11px]">
                {nodes
                  .filter((node) => {
                    const category = nodeCategory(node);
                    return (
                      visibleElements.some((element) => element.data.id === node.id) &&
                      category !== "evidence" &&
                      category !== "event"
                    );
                  })
                  .slice(0, 40)
                  .map((node) => (
                    <li key={node.id}>
                      <button
                        type="button"
                        onClick={() =>
                          setSelected({
                            kind: "node",
                            data: {
                              ...node.data,
                              id: node.id,
                              label: node.label,
                              node_type: node.node_type,
                              category: nodeCategory(node),
                              type_label:
                                NODE_LABELS[nodeCategory(node)] ?? humanize(nodeCategory(node)),
                            },
                          })
                        }
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-secondary transition hover:bg-surface-2/60 hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                      >
                        <span className="text-[9px] uppercase tracking-wider text-muted">
                          {NODE_LABELS[nodeCategory(node)] ?? humanize(nodeCategory(node))}
                        </span>
                        <span className="truncate">{node.label}</span>
                      </button>
                    </li>
                  ))}
              </ul>
              {visibleElements.length === 0 ? (
                <p className="text-[11px] text-muted">No nodes match the current filters.</p>
              ) : null}
            </CardBody>
          </Card>

          <Card data-tour="graph-legend">
            <CardHeader title="Legend" subtitle="Shape and colour identify entity types" />
            <CardBody className="space-y-2 text-[11px] text-muted">
              <LegendShape color={nodeColors.evidence} label="Evidence file" icon={iconFor("evidence")} />
              <LegendShape color={nodeColors.phone} label="Phone number" icon={iconFor("phone")} />
              <LegendShape color={nodeColors.device} label="Device" icon={iconFor("device")} />
              <LegendShape color={nodeColors.upi_vpa} label="UPI / account identifier" icon={iconFor("upi_vpa")} />
              <LegendShape color={nodeColors.ip} label="IP address" icon={iconFor("ip")} />
              <LegendShape color={nodeColors.username} label="User account" icon={iconFor("username")} />
              <LegendShape color={nodeColors.email} label="Email address" icon={iconFor("email")} />
              <LegendShape color={nodeColors.default} label="Other entity" icon={iconFor("default")} />
              <div className="my-2 h-px bg-surface-2" />
              <LegendLine color={palette.exact} label="Exact identifier / documented" />
              <LegendLine color={palette.conflict} label="Conflict or discrepancy" />
              <LegendLine color={palette.heuristic} dashed label="Heuristic lead" />
              <LegendLine color={palette.edge} label="Extraction / containment" />
            </CardBody>
          </Card>

          <Card data-tour="graph-selection">
            <CardHeader title="Selection" subtitle="Click a node or a line to understand it" />
            <CardBody>
              {!selected && focusType === "relationship" && focusId ? (
                <RelationshipEvidencePanel caseId={caseId} relationshipId={focusId} />
              ) : !selected ? (
                <p className="text-xs leading-relaxed text-muted">
                  Select a node to see what it represents, or select a line to see
                  the evidence behind the connection.
                </p>
              ) : selected.kind === "edge" &&
                typeof selected.data.relationship_id === "string" ? (
                <RelationshipEvidencePanel
                  caseId={caseId}
                  relationshipId={selected.data.relationship_id}
                />
              ) : (
                <SelectionPanel
                  caseId={caseId}
                  selected={selected}
                  nodes={nodes}
                  edges={edges}
                  evidenceNames={evidenceNames}
                  neighbourFocus={neighbourFocus}
                  onToggleNeighbour={() => setNeighbourFocus((current) => !current)}
                />
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

function SelectionPanel({
  caseId,
  selected,
  nodes,
  edges,
  evidenceNames,
  neighbourFocus,
  onToggleNeighbour,
}: {
  caseId: string;
  selected: SelectedElement;
  nodes: GraphNode[];
  edges: GraphEdge[];
  evidenceNames: Map<string, string>;
  neighbourFocus: boolean;
  onToggleNeighbour: () => void;
}) {
  const nodeId = String(selected.data.id);
  const isNode = selected.kind === "node";
  const entityId =
    isNode && String(selected.data.node_type) === "entity"
      ? String(selected.data.entity_id ?? "")
      : "";
  const entityQuery = useEntityDetail(caseId, entityId || null);
  const category = isNode
    ? String(selected.data.category ?? selected.data.node_type ?? "node")
    : "connection";

  const incident = useMemo(
    () =>
      isNode
        ? edges.filter((edge) => edge.source === nodeId || edge.target === nodeId)
        : [],
    [edges, isNode, nodeId],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="border-accent/30 bg-accent/10 text-accent">
          {isNode ? "Node" : "Connection"}
        </Badge>
        <Badge className="border-line-strong bg-surface-2/70 capitalize text-secondary">
          {NODE_LABELS[category] ?? humanize(category)}
        </Badge>
        {selected.data.classification ? (
          <Badge className="border-line-strong bg-surface-2/70 capitalize text-muted">
            {humanize(String(selected.data.classification))}
          </Badge>
        ) : null}
      </div>

      {isNode ? (
        <>
          <div>
            <p className="text-sm font-medium text-primary">
              {String(selected.data.label ?? selected.data.id)}
            </p>
            <p className="mt-0.5 text-[11px] leading-relaxed text-muted">
              This is a {String(
                selected.data.type_label ?? NODE_LABELS[category] ?? category,
              ).toLowerCase()} recorded in this case.
            </p>
          </div>

          {entityQuery.data ? (
            <dl className="grid grid-cols-2 gap-2 rounded-lg border border-line bg-surface-2/40 p-2.5 text-[11px]">
              <div>
                <dt className="text-muted">Mentions</dt>
                <dd className="font-mono text-secondary">{entityQuery.data.mention_count}</dd>
              </div>
              <div>
                <dt className="text-muted">Evidence sources</dt>
                <dd className="font-mono text-secondary">
                  {entityQuery.data.evidence_ids.length}
                </dd>
              </div>
              {entityQuery.data.entity.first_seen_at ? (
                <div className="col-span-2">
                  <dt className="text-muted">First seen</dt>
                  <dd className="text-secondary">
                    {formatDateTime(entityQuery.data.entity.first_seen_at)}
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          <div>
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Connected to {incident.length} record{incident.length === 1 ? "" : "s"}
            </p>
            <ul className="max-h-52 space-y-1.5 overflow-auto pr-1">
              {incident.slice(0, 12).map((edge) => {
                const other = edge.source === nodeId ? edge.target : edge.source;
                const otherNode = nodes.find((node) => node.id === other);
                return (
                  <li
                    key={edge.id}
                    className="rounded-lg border border-line bg-surface-2/40 px-2.5 py-1.5 text-[11px]"
                  >
                    <p className="font-medium text-secondary">{edge.label}</p>
                    <p className="mt-0.5 text-muted">
                      {otherNode?.label ?? other.replace(/^[^:]+:/, "")}
                    </p>
                  </li>
                );
              })}
              {incident.length === 0 ? (
                <li className="text-[11px] text-muted">
                  No documented connections for this node.
                </li>
              ) : null}
            </ul>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={onToggleNeighbour}>
              {neighbourFocus ? "Show full graph" : "Focus on this entity"}
            </Button>
            {entityId ? (
              <Link to={`/cases/${caseId}/entities?entityId=${entityId}`}>
                <Button size="sm" variant="ghost" icon={<ArrowRight size={12} />}>
                  Open entity
                </Button>
              </Link>
            ) : null}
            <Link to={`/cases/${caseId}/timeline`}>
              <Button size="sm" variant="ghost">
                Timeline
              </Button>
            </Link>
          </div>
        </>
      ) : (
        <>
          <div>
            <p className="text-sm font-medium text-primary">
              {String(selected.data.label ?? "Connection")}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-secondary">
              {String(selected.data.explanation ?? "No explanation stored.")}
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-2 rounded-lg border border-line bg-surface-2/40 p-2.5 text-[11px]">
            <div>
              <dt className="text-muted">Kind</dt>
              <dd className="text-secondary">
                {String(selected.data.match_method ?? "unknown")}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Confidence</dt>
              <dd className="text-secondary">
                {humanize(String(selected.data.confidence ?? "unknown"))}
              </dd>
            </div>
          </dl>
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Supporting evidence
            </p>
            <ul className="space-y-1 text-[11px] text-muted">
              {(
                (selected.data.supporting_evidence_ids as string[] | undefined) ?? []
              ).slice(0, 8).map((id) => (
                <li key={id}>
                  <Link
                    to={`/cases/${caseId}/evidence?evidenceId=${id}`}
                    className="text-accent hover:text-accent-strong"
                  >
                    {evidenceNames.get(id) ?? id}
                  </Link>
                </li>
              ))}
              {((selected.data.supporting_evidence_ids as string[] | undefined) ?? [])
                .length === 0 ? <li>No linked evidence recorded.</li> : null}
            </ul>
          </div>
          {selected.data.match_method === "heuristic" ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-2.5 text-[11px] leading-relaxed text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80">
              <Info size={12} className="mr-1 inline" />
              This line is a heuristic lead, not a proven relationship.
            </div>
          ) : null}
        </>
      )}
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

function LegendLine({
  color,
  label,
  dashed,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="h-0.5 w-6"
        style={{
          backgroundImage: dashed
            ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 8px)`
            : undefined,
          backgroundColor: dashed ? undefined : color,
        }}
      />
      <span>{label}</span>
    </div>
  );
}

function LegendShape({
  color,
  label,
  icon,
}: {
  color: string;
  label: string;
  icon: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px]"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      >
        <img src={icon} alt="" className="h-3 w-3" />
      </span>
      <span>{label}</span>
    </div>
  );
}

/**
 * Layout options tuned for readability rather than compactness.
 *
 * Real investigations produce dense graphs, so nodes get generous separation
 * and labels are placed to avoid sitting on top of each other.
 */
function layoutOptions(name: string): cytoscape.LayoutOptions {
  if (name === "cose") {
    return {
      name: "cose",
      animate: false,
      fit: true,
      padding: 44,
      nodeRepulsion: () => 12000,
      idealEdgeLength: () => 90,
      edgeElasticity: () => 90,
      gravity: 0.9,
      numIter: 1200,
      componentSpacing: 70,
      nodeOverlap: 18,
    } as cytoscape.LayoutOptions;
  }
  if (name === "breadthfirst") {
    return {
      name: "breadthfirst",
      directed: true,
      padding: 40,
      spacingFactor: 1.35,
      avoidOverlap: true,
    } as cytoscape.LayoutOptions;
  }
  if (name === "circle") {
    return { name: "circle", padding: 40, avoidOverlap: true } as cytoscape.LayoutOptions;
  }
  return { name: "grid", padding: 40, avoidOverlap: true } as cytoscape.LayoutOptions;
}

function CytoscapeCanvas({
  elements,
  layout,
  mode,
  onSelect,
  onHover,
}: {
  elements: ElementDefinition[];
  layout: string;
  mode: GraphMode;
  onSelect: (selected: SelectedElement | null) => void;
  onHover: (text: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const { theme } = useTheme();
  const palette = GRAPH_PALETTES[theme];
  const simple = mode === "simple";

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
            "background-image": "data(icon)",
            "background-fit": "none",
            "background-width": 13,
            "background-height": 13,
            "background-position-x": "50%",
            "background-position-y": "50%",
            label: "data(label)",
            color: palette.label,
            "font-size": 9,
            "font-weight": 500,
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 6,
            "text-wrap": "ellipsis",
            "text-max-width": "96px",
            "text-background-color": palette.labelBg,
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
            "text-background-shape": "roundrectangle",
            width: 26,
            height: 26,
            "border-width": 1.5,
            "border-color": palette.nodeBorder,
            "overlay-opacity": 0,
          },
        },
        ...Object.entries(NODE_SHAPES).map(([category, shape]) => ({
          selector: `node[category = "${category}"]`,
          style: { shape: shape as cytoscape.Css.NodeShape },
        })),
        {
          selector: 'node[node_type = "evidence"]',
          style: {
            width: 34,
            height: 30,
            "background-width": 15,
            "background-height": 15,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.3,
            "line-color": palette.edge,
            "target-arrow-color": palette.edge,
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.7,
            "curve-style": "bezier",
            "control-point-step-size": 44,
            opacity: 0.75,
            label: simple ? "data(label)" : "",
            "font-size": 7,
            "min-zoomed-font-size": 9,
            "text-rotation": "autorotate",
            "text-background-color": palette.edgeLabelBg,
            "text-background-opacity": 0.92,
            "text-background-padding": "3px",
            "text-background-shape": "roundrectangle",
            color: palette.edgeLabel,
            "text-max-width": "110px",
            "text-wrap": "ellipsis",
            "text-overflow-wrap": "whitespace",
            "overlay-opacity": 0,
          },
        },
        {
          // Labels disappear before they can collide in a dense graph.
          selector: "node[label]",
          style: { "min-zoomed-font-size": 8 },
        },
        {
          selector: 'edge[relationship_type = "shared_identifier"]',
          style: {
            width: 2.4,
            "line-color": palette.exact,
            "target-arrow-color": palette.exact,
          },
        },
        {
          selector: 'edge[relationship_type = "co_mention"]',
          style: {
            width: 1.6,
            "line-style": "dashed",
            "line-color": palette.heuristic,
            "target-arrow-color": palette.heuristic,
          },
        },
        {
          selector: 'edge[relationship_type = "temporal_association"]',
          style: {
            width: 1.5,
            "line-style": "dashed",
            "line-color": palette.heuristic,
            "target-arrow-color": palette.heuristic,
          },
        },
        {
          selector: 'edge[relationship_type = "spatial_proximity"]',
          style: {
            width: 2,
            "line-style": "dotted",
            "line-color": palette.heuristic,
            "target-arrow-color": palette.heuristic,
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
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": palette.selection,
            "underlay-color": palette.selection,
            "underlay-opacity": 0.18,
            "underlay-padding": 8,
          },
        },
        {
          selector: "edge:selected",
          style: { width: 2.6, opacity: 1, "line-color": palette.selection, "target-arrow-color": palette.selection },
        },
        {
          selector: ".tour-hover",
          style: { "underlay-color": palette.selection, "underlay-opacity": 0.12, "underlay-padding": 6 },
        },
      ],
      layout: layoutOptions("cose"),
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
    cy.on("mouseover", "edge", (event) => {
      onHover(String(event.target.data("explanation") ?? ""));
    });
    cy.on("mouseout", "edge", () => onHover(null));
    cy.on("mouseover", "node", (event) => {
      onHover(
        `${String(event.target.data("type_label") ?? "Node")}: ${String(
          event.target.data("label") ?? "",
        )}`,
      );
    });
    cy.on("mouseout", "node", () => onHover(null));

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [onSelect, onHover, theme, palette, simple]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().remove();
    cy.add(elements);
    const layoutInstance = cy.layout(layoutOptions(layout));
    layoutInstance.run();
    layoutInstance.one("layoutstop", () => cy.fit(undefined, 40));
  }, [elements, layout]);

  return <div ref={containerRef} className="graph-canvas h-[420px] w-full sm:h-[620px]" />;
}
