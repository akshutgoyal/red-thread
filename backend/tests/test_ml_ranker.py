from __future__ import annotations

from app.services import ml_ranker
from app.services.relationship_engine import build_case_relationships
from app.models import Case, Entity, Event, EventEntity, Evidence


def test_shared_identifier_outranks_co_mention():
    strong = ml_ranker.rank_relationship(
        "shared_identifier", {"entity_type": "phone"}, support_count=2
    )
    weak = ml_ranker.rank_relationship("co_mention", {}, support_count=2)
    assert strong.score > weak.score
    assert 0.0 <= strong.score <= 1.0
    assert 0.0 <= weak.score <= 1.0


def test_unsupported_relationship_scores_zero_not_negative():
    score = ml_ranker.rank_relationship("co_mention", {}, support_count=0)
    assert score.score >= 0.0


def test_score_is_deterministic():
    first = ml_ranker.rank_relationship(
        "temporal_association",
        {"delta_seconds": 60, "window_seconds": 600},
        support_count=2,
    )
    second = ml_ranker.rank_relationship(
        "temporal_association",
        {"delta_seconds": 60, "window_seconds": 600},
        support_count=2,
    )
    assert first.score == second.score
    assert first.features == second.features


def test_closer_in_time_scores_higher():
    near = ml_ranker.rank_relationship(
        "temporal_association",
        {"delta_seconds": 10, "window_seconds": 600},
        support_count=2,
    )
    far = ml_ranker.rank_relationship(
        "temporal_association",
        {"delta_seconds": 590, "window_seconds": 600},
        support_count=2,
    )
    assert near.score > far.score


def test_metadata_never_claims_probability_of_guilt():
    payload = ml_ranker.LeadScore(score=0.4).as_metadata()
    assert payload["detection_method"] == "deterministic+ml_ranked"
    assert "guilt" in payload["interpretation"]
    assert "not a probability" in payload["interpretation"].lower()


def test_cross_source_corroboration_increases_score():
    single = ml_ranker.rank_relationship(
        "co_mention", {}, support_count=2, distinct_evidence_ids={"e1"}
    )
    cross = ml_ranker.rank_relationship(
        "co_mention", {}, support_count=2, distinct_evidence_ids={"e1", "e2"}
    )
    assert cross.score > single.score


def test_engine_persists_ml_assist_without_changing_type(db):
    case = Case(title="ML ranker case", description="Synthetic")
    db.add(case)
    db.flush()
    evidence = Evidence(
        case_id=case.id,
        original_filename="cdr.csv",
        stored_filename="cdr.csv",
        relative_path="evidence/cdr.csv",
        media_type="text/csv",
        size_bytes=10,
        sha256="b" * 64,
        processing_status="parsed",
        parser_name="cdr",
    )
    db.add(evidence)
    db.flush()
    other_evidence = Evidence(
        case_id=case.id,
        original_filename="payments.csv",
        stored_filename="payments.csv",
        relative_path="evidence/payments.csv",
        media_type="text/csv",
        size_bytes=10,
        sha256="c" * 64,
        processing_status="parsed",
        parser_name="bank",
    )
    db.add(other_evidence)
    db.flush()
    entity = Entity(
        case_id=case.id,
        entity_type="phone",
        value_original="+91-99001-12233",
        value_normalized="+919900112233",
    )
    db.add(entity)
    db.flush()
    events = []
    for index in range(2):
        event = Event(
            case_id=case.id,
            evidence_id=evidence.id if index == 0 else other_evidence.id,
            event_type="call",
            timestamp_raw=f"2026-01-0{index + 1} 10:00:00",
            timestamp_normalized=__import__("datetime").datetime(
                2026, 1, index + 1, 10, 0, tzinfo=__import__("datetime").timezone.utc
            ),
            timestamp_confidence="exact",
            source_filename="cdr.csv",
            source_locator=f"row:{index + 2}",
            source_snippet="call record",
            attributes_json={},
            warnings_json=[],
            parser_name="cdr",
            parser_version="1.0.0",
        )
        db.add(event)
        db.flush()
        db.add(
            EventEntity(event_id=event.id, entity_id=entity.id, role="caller")
        )
        events.append(event)
    db.commit()

    build_case_relationships(db, case.id)
    db.commit()

    from sqlalchemy import select as sa_select

    from app.models import Relationship

    rows = list(
        db.scalars(sa_select(Relationship).where(Relationship.case_id == case.id))
    )
    assert rows, "the deterministic engine should still produce relationships"
    for row in rows:
        assist = (row.metadata_json or {}).get("ml_assist")
        assert assist is not None, f"{row.relationship_type} was not scored"
        assert assist["detection_method"] == "deterministic+ml_ranked"
        assert 0.0 <= assist["score"] <= 1.0
        # The rule still owns the type and classification.
        assert row.relationship_type in {
            "shared_identifier",
            "co_mention",
            "temporal_association",
            "spatial_proximity",
            "communication_sequence",
            "device_auth_context",
            "geo_velocity_anomaly",
            "cctv_coverage_gap",
        }
        assert row.classification in {"observation", "correlation", "inference", "hypothesis"}
