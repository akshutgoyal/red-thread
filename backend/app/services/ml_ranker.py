"""Lightweight, explainable relationship scoring.

This is deliberately not a trained model. It is a fixed-weight linear scorer over
features the deterministic engine already computed, which means:

* it adds no dependency, no training pipeline and no model artefact;
* the same input always yields the same score;
* every contribution can be shown to an investigator.

The score ranks investigative leads. It is **not** a probability of guilt,
fraud, identity or causation, and it never changes a relationship's type or
classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ENGINE = "linear_feature_scorer_v1"

#: Weights are hand-set from forensic reasoning, not fitted. Positive weights
#: increase the score; the constants are documented so an investigator can audit
#: why a lead ranked where it did.
WEIGHTS = {
    # Two records sharing a real identifier is the strongest available signal.
    "shared_identifier": 0.42,
    # Co-mention in one event is weaker: the same document naming two people is
    # not evidence they interacted.
    "co_mention": 0.12,
    # Temporal proximity contributes less as the gap widens.
    "temporal": 0.14,
    # Spatial proximity likewise.
    "spatial": 0.14,
    # A repeated interaction pattern across many events.
    "repetition": 0.16,
    # Authentication and device context implying a shared operator.
    "device_auth": 0.18,
    # Corroboration by independent evidence sources.
    "cross_source": 0.10,
    # A rule that fired without any supporting locator is a weak lead.
    "unsupported_penalty": -0.25,
}

RELATIONSHIP_FEATURES: dict[str, set[str]] = {
    "shared_identifier": {"shared_identifier"},
    "co_mention": {"co_mention"},
    "temporal_association": {"shared_identifier", "temporal"},
    "spatial_proximity": {"spatial", "temporal"},
    "communication_sequence": {"repetition", "shared_identifier", "temporal"},
    "device_auth_context": {"device_auth", "shared_identifier"},
    "geo_velocity_anomaly": {"spatial", "temporal"},
    "cctv_coverage_gap": {"temporal"},
}


@dataclass(frozen=True)
class LeadScore:
    """An explainable match score for one deterministic relationship."""

    score: float
    features: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    engine: str = ENGINE

    def as_metadata(self) -> dict[str, Any]:
        """Serialised under ``metadata_json['ml_assist']``. No migration needed."""

        return {
            "detection_method": "deterministic+ml_ranked",
            "engine": self.engine,
            "score": round(self.score, 4),
            "features": {key: round(value, 4) for key, value in self.features.items()},
            "explanation": self.explanation,
            "interpretation": (
                "Ranking signal only. Not a probability of guilt, fraud, identity "
                "or causation."
            ),
        }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _temporal_feature(delta_seconds: float | None, window_seconds: float | None) -> float:
    if not delta_seconds or not window_seconds or window_seconds <= 0:
        return 0.0
    # Closer in time scores higher, decaying linearly across the window.
    return _clamp(1.0 - (delta_seconds / window_seconds))


def _spatial_feature(distance_m: float | None, radius_m: float | None) -> float:
    if distance_m is None or not radius_m or radius_m <= 0:
        return 0.0
    return _clamp(1.0 - (distance_m / radius_m))


def rank_relationship(
    relationship_type: str,
    metadata: dict[str, Any],
    *,
    support_count: int,
    distinct_evidence_ids: set[str] | None = None,
) -> LeadScore:
    """Score one deterministic relationship from its stored metadata.

    Reads only what the engine already recorded, so ranking never invents a
    fact that the rule did not establish.
    """

    active = set(RELATIONSHIP_FEATURES.get(relationship_type, set()))
    features: dict[str, float] = {}

    if "shared_identifier" in active:
        # A normalized exact match rather than a fuzzy one.
        features["shared_identifier"] = WEIGHTS["shared_identifier"]

    if "co_mention" in active:
        features["co_mention"] = WEIGHTS["co_mention"]

    if "temporal" in active:
        weight = _temporal_feature(
            metadata.get("delta_seconds"), metadata.get("window_seconds")
        )
        if weight:
            features["temporal"] = WEIGHTS["temporal"] * weight

    if "spatial" in active:
        weight = _spatial_feature(metadata.get("distance_m"), metadata.get("radius_m"))
        if weight:
            features["spatial"] = WEIGHTS["spatial"] * weight

    if "repetition" in active:
        event_count = metadata.get("event_count") or 2
        features["repetition"] = WEIGHTS["repetition"] * _clamp(
            float(event_count) / 10.0
        )

    if "device_auth" in active:
        features["device_auth"] = WEIGHTS["device_auth"]

    if distinct_evidence_ids and len(distinct_evidence_ids) > 1:
        features["cross_source"] = WEIGHTS["cross_source"]

    if support_count == 0:
        features["unsupported_penalty"] = WEIGHTS["unsupported_penalty"]

    score = _clamp(sum(features.values()))

    if not features:
        explanation = "No scoring features applied to this relationship type."
    else:
        parts = ", ".join(
            f"{name} {value:+.2f}" for name, value in sorted(features.items())
        )
        explanation = f"Match score {score:.2f} from: {parts}."

    return LeadScore(score=score, features=features, explanation=explanation)


DETECTION_DETERMINISTIC = "deterministic"
DETECTION_RANKED = "deterministic+ml_ranked"
