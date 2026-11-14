"""Count consistency between the workspace guidance and the relationship graph.

The two surfaces previously disagreed because the graph summed derived edges
(containment, extraction, temporal) while the workspace counted only persisted
relationships. These tests pin the shared definitions so that cannot regress.
"""

from __future__ import annotations

from app.services.count_service import DOCUMENTED_CLASSIFICATIONS
from app.services.relationship_service import upsert_relationship


def _counts(client, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/guidance")
    assert response.status_code == 200, response.text
    return response.json()["summary"]


def _graph(client, case_id: str) -> dict:
    response = client.get(f"/api/cases/{case_id}/graph")
    assert response.status_code == 200, response.text
    return response.json()


def _link(db, case_id: str, *, source: str, target: str, kind: str, rule: str):
    return upsert_relationship(
        db,
        case_id=case_id,
        source_type="entity",
        source_id=source,
        target_type="entity",
        target_id=target,
        relationship_type=kind,
        correlation_rule=rule,
        explanation="Test relationship.",
        confidence="high",
        classification="correlation",
    )


def test_graph_and_guidance_report_the_same_relationship_total(client, db, case):
    """The workspace and graph must agree on how many relationships exist."""

    _link(db, case["id"], source="phone-a", target="phone-b", kind="shared_identifier", rule="exact_match")

    summary = _counts(client, case["id"])
    graph = _graph(client, case["id"])

    assert graph["counts"]["total_relationships"] == summary["total_relationships"]
    assert graph["counts"]["documented_relationships"] == summary["documented_relationships"]
    assert graph["counts"]["inferred_leads"] == summary["inferred_leads"]
    assert graph["counts"]["unique_connections"] == summary["unique_connections"]


def test_graph_counts_match_stored_rows(client, db, case):
    """Graph counts describe stored relationships, not rendered edges."""

    _link(db, case["id"], source="phone-a", target="phone-b", kind="shared_identifier", rule="exact_match")

    counts = _graph(client, case["id"])["counts"]

    assert counts["total_relationships"] == 1
    assert counts["documented_relationships"] == 1
    assert counts["inferred_leads"] == 0
    # The rendered graph also carries structural edges, so edges exceed these.
    assert counts["total_edges"] >= counts["total_relationships"]


def test_duplicate_pairs_are_counted_once(client, db, case):
    """Two rules describing the same entity pair are one unique connection."""

    _link(db, case["id"], source="phone-a", target="phone-b", kind="shared_identifier", rule="rule_one")
    _link(db, case["id"], source="phone-b", target="phone-a", kind="co_mention", rule="rule_two")

    counts = _graph(client, case["id"])["counts"]

    assert counts["total_relationships"] == 2
    # A→B and B→A are the same pair, so unique connections stays at one.
    assert counts["unique_connections"] == 1


def test_counts_are_case_scoped(client, db, case):
    """A second case must not inflate the first case's counts."""

    other = client.post("/api/cases", json={"title": "Second case"}).json()
    _link(db, other["id"], source="device-x", target="device-y", kind="shared_identifier", rule="exact_match")

    first = _graph(client, case["id"])["counts"]
    second = _graph(client, other["id"])["counts"]

    assert first["total_relationships"] == 0
    assert second["total_relationships"] == 1


def test_visible_counts_belong_to_the_canvas(client, db, case):
    """Canvas counts are a subset of the stored totals, never larger."""

    _link(db, case["id"], source="phone-a", target="phone-b", kind="shared_identifier", rule="exact_match")

    counts = _graph(client, case["id"])["counts"]

    assert counts["entity_nodes"] <= counts["total_nodes"]
    assert counts["temporal_edges"] <= counts["total_edges"]
    assert counts["entities_in_case"] >= 0


def test_documented_and_inferred_are_disjoint(client, db, case):
    """The two classifications must not double-count a relationship."""

    _link(db, case["id"], source="phone-a", target="phone-b", kind="shared_identifier", rule="exact_match")

    counts = _graph(client, case["id"])["counts"]

    assert (
        counts["documented_relationships"] + counts["inferred_leads"]
        <= counts["total_relationships"]
    )
    assert "correlation" in DOCUMENTED_CLASSIFICATIONS


def test_entity_totals_agree_across_surfaces(client, db, case):
    """The workspace entity count and the graph's in-case count are the same."""

    summary = _counts(client, case["id"])
    counts = _graph(client, case["id"])["counts"]

    assert summary["entities"] == counts["entities_in_case"]


def test_entity_nodes_never_exceed_entities_in_case(client, db, case):
    """Only entities that are actually in the case can become nodes."""

    counts = _graph(client, case["id"])["counts"]

    assert counts["entity_nodes"] <= counts["entities_in_case"]
    assert counts["entities_with_events"] <= counts["entities_in_case"]
