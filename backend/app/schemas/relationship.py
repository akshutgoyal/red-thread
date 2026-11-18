from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

RelationshipClassification = Literal["observation", "correlation", "inference", "hypothesis"]
RelationshipReviewStatus = Literal[
    "unreviewed", "needs_review", "accepted", "rejected", "needs_more_evidence"
]
RelationshipDecision = Literal["needs_review", "accepted", "rejected", "needs_more_evidence"]
AnnotationTargetType = Literal[
    "case", "evidence", "event", "entity", "finding", "relationship", "graph_edge"
]


class RelationshipSupportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_id: str | None = None
    event_id: str | None = None
    finding_id: str | None = None
    source_locator: str = ""
    snippet: str = ""
    support_kind: str = "evidence"
    created_at: datetime


class ReviewDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    target_type: str
    target_id: str
    decision: str
    reviewer: str
    note: str
    created_at: datetime


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship_type: str
    correlation_rule: str
    explanation: str
    confidence: str
    classification: RelationshipClassification
    review_status: RelationshipReviewStatus
    review_note: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    support_count: int = 0
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def detection_method(self) -> str:
        """How this relationship was found.

        ``deterministic`` when a rule alone established it, and
        ``deterministic+ml_ranked`` when the lightweight scorer also ran. It is
        never ``ml`` alone: the scorer cannot create a relationship.
        """

        assist = self.metadata_json.get("ml_assist") or {}
        return str(assist.get("detection_method") or "deterministic")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def match_score(self) -> float | None:
        """Ranking signal in [0, 1]. Never a probability of guilt or fraud."""

        assist = self.metadata_json.get("ml_assist") or {}
        score = assist.get("score")
        return float(score) if isinstance(score, (int, float)) else None


class RelationshipDetail(RelationshipRead):
    supports: list[RelationshipSupportRead] = Field(default_factory=list)
    reviews: list[ReviewDecisionRead] = Field(default_factory=list)


class RelationshipListResponse(BaseModel):
    items: list[RelationshipRead]
    total: int


class RelationshipReviewRequest(BaseModel):
    decision: RelationshipDecision
    reviewer: str = ""
    note: str = ""


class AnnotationCreate(BaseModel):
    target_type: AnnotationTargetType
    target_id: str = Field(min_length=1, max_length=128)
    author: str = Field(default="investigator", max_length=128)
    note: str = Field(min_length=1)


class AnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    target_type: str
    target_id: str
    author: str
    note: str
    created_at: datetime
