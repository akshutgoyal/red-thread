from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, new_id, utcnow


class Relationship(Base, TimestampMixin):
    """A persisted, explainable connection between two records.

    This is intentionally additive to the legacy GraphEdge model.  A
    relationship carries its rule, provenance and human review state so the
    graph can explain every edge instead of returning an opaque link.
    """

    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relationship_type",
            "correlation_rule",
            name="uq_relationship_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correlation_rule: Mapped[str] = mapped_column(String(128), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    classification: Mapped[str] = mapped_column(
        String(32), default="correlation", nullable=False, index=True
    )
    review_status: Mapped[str] = mapped_column(
        String(32), default="unreviewed", nullable=False, index=True
    )
    review_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    supports: Mapped[list[RelationshipSupport]] = relationship(
        back_populates="relationship",
        cascade="all, delete-orphan",
        order_by="RelationshipSupport.created_at",
    )

    @property
    def support_count(self) -> int:
        return len(self.supports)


class RelationshipSupport(Base):
    """A concrete source record backing a relationship.

    Evidence is the anchor; event/finding links are optional because some
    relationships are supported by an evidence-level identifier rather than a
    single parsed event.  Source locator and snippet keep the original row
    inspectable.
    """

    __tablename__ = "relationship_supports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("relationships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    finding_id: Mapped[str | None] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_locator: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    support_kind: Mapped[str] = mapped_column(String(64), default="evidence", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    relationship: Mapped[Relationship] = relationship(back_populates="supports")


class ReviewDecision(Base):
    """Immutable human review history for a relationship or another record."""

    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewer: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class InvestigatorAnnotation(Base):
    """Investigator-authored note attached to any investigative record."""

    __tablename__ = "investigator_annotations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(128), default="investigator", nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
