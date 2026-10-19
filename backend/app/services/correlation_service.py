from __future__ import annotations

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Event, EventEntity, Evidence, GraphEdge
from ..schemas.event import GraphEdgeRead, GraphNodeRead, GraphResponse


def build_graph(
    db: Session,
    case_id: str,
    limit: int = 500,
    *,
    include_temporal: bool = False,
    temporal_window_seconds: int = 300,
) -> GraphResponse:
    """Build a provenance and correlation graph for a case.

    Containment and extraction edges are derived from stored events. Exact
    matches and conflicts are read from persisted ``GraphEdge`` rows created by
    the reconciliation service. Temporal-proximity edges are optional and are
    always labelled as heuristic leads, never as proof.
    """
    graph = nx.MultiDiGraph()
    evidence_rows = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case_id)
            .order_by(Evidence.uploaded_at)
        )
    )
    for evidence in evidence_rows:
        graph.add_node(
            f"evidence:{evidence.id}",
            label=evidence.original_filename,
            node_type="evidence",
            data={
                "evidence_id": evidence.id,
                "processing_status": evidence.processing_status,
                "sha256": evidence.sha256,
            },
        )

    events = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case_id)
            .options(selectinload(Event.entity_links).selectinload(EventEntity.entity))
            .order_by(Event.timestamp_normalized.is_(None), Event.timestamp_normalized)
            .limit(limit)
        )
    )
    for event in events:
        event_node = f"event:{event.id}"
        graph.add_node(
            event_node,
            label=f"{event.event_type} @ {event.timestamp_raw or 'undated'}",
            node_type="event",
            data={
                "event_id": event.id,
                "event_type": event.event_type,
                "source_locator": event.source_locator,
                "timestamp_confidence": event.timestamp_confidence,
            },
        )
        graph.add_edge(
            f"evidence:{event.evidence_id}",
            event_node,
            edge_type="evidence_contains_event",
            match_method="containment",
            explanation="Event extracted from this evidence file.",
            confidence="exact",
            supporting_event_ids=[event.id],
            supporting_evidence_ids=[event.evidence_id],
        )
        for link in event.entity_links:
            entity = link.entity
            entity_node = f"entity:{entity.id}"
            if entity_node not in graph:
                graph.add_node(
                    entity_node,
                    label=entity.value_original,
                    node_type="entity",
                    data={
                        "entity_id": entity.id,
                        "entity_type": entity.entity_type,
                        "value_normalized": entity.value_normalized,
                    },
                )
            graph.add_edge(
                event_node,
                entity_node,
                edge_type=f"event_mentions_{link.role}",
                match_method="extraction",
                explanation=(
                    f"Entity '{entity.value_original}' extracted from event "
                    f"{event.source_locator}."
                ),
                confidence="exact",
                supporting_event_ids=[event.id],
                supporting_evidence_ids=[event.evidence_id],
            )

    persisted = list(db.scalars(select(GraphEdge).where(GraphEdge.case_id == case_id)))
    for edge in persisted:
        for node_id, node_type in (
            (edge.source_id, edge.source_type),
            (edge.target_id, edge.target_type),
        ):
            if node_id not in graph:
                graph.add_node(
                    node_id,
                    label=node_id.split(":", 1)[-1],
                    node_type=node_type,
                    data={},
                )
        graph.add_edge(
            edge.source_id,
            edge.target_id,
            edge_type=edge.edge_type,
            match_method=edge.match_method,
            explanation=edge.explanation,
            confidence=edge.confidence,
            supporting_event_ids=edge.supporting_event_ids_json or [],
            supporting_evidence_ids=edge.supporting_evidence_ids_json or [],
            persisted_edge_id=edge.id,
        )

    if include_temporal:
        timed = [event for event in events if event.timestamp_normalized is not None]
        temporal_count = 0
        for index, source in enumerate(timed):
            for target in timed[index + 1 :]:
                delta = abs(
                    (
                        target.timestamp_normalized - source.timestamp_normalized
                    ).total_seconds()
                )
                if delta > temporal_window_seconds:
                    break
                if delta == 0 or source.evidence_id == target.evidence_id:
                    continue
                graph.add_edge(
                    f"event:{source.id}",
                    f"event:{target.id}",
                    edge_type="temporal_proximity",
                    match_method="heuristic",
                    explanation=(
                        f"Events occur within {int(delta)} seconds of each other. "
                        "This is a lead for further investigation, not proof of a connection."
                    ),
                    confidence="low",
                    supporting_event_ids=[source.id, target.id],
                    supporting_evidence_ids=sorted(
                        {source.evidence_id, target.evidence_id}
                    ),
                    temporal_seconds=int(delta),
                )
                temporal_count += 1
                if temporal_count >= 100:
                    break
            if temporal_count >= 100:
                break

    nodes: list[GraphNodeRead] = []
    for node_id, data in graph.nodes(data=True):
        nodes.append(
            GraphNodeRead(
                id=node_id,
                label=data.get("label", node_id),
                node_type=data.get("node_type", "unknown"),
                data=data.get("data", {}),
            )
        )

    edges: list[GraphEdgeRead] = []
    for index, (source, target, data) in enumerate(graph.edges(data=True), start=1):
        edge_id = data.get("persisted_edge_id") or f"edge:{index}"
        edges.append(
            GraphEdgeRead(
                id=edge_id,
                source=source,
                target=target,
                label=data.get("edge_type", "related"),
                edge_type=data.get("edge_type", "related"),
                match_method=data.get("match_method", "unknown"),
                explanation=data.get("explanation", ""),
                confidence=data.get("confidence", "medium"),
                supporting_event_ids=data.get("supporting_event_ids", []),
                supporting_evidence_ids=data.get("supporting_evidence_ids", []),
            )
        )
    return GraphResponse(nodes=nodes, edges=edges)
