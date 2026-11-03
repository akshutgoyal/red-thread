from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import new_id, utcnow

if TYPE_CHECKING:
    from .case import Case
    from .evidence import Evidence
    from .finding import FindingEvidence


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp_normalized: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    timestamp_confidence: Mapped[str] = mapped_column(
        String(32), default="unknown", nullable=False, index=True
    )
    timestamp_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_locator: Mapped[str] = mapped_column(String(128), nullable=False)
    source_snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attributes_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    case: Mapped[Case] = relationship(back_populates="events")
    evidence: Mapped[Evidence] = relationship(back_populates="events")
    entity_links: Mapped[list[EventEntity]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    finding_links: Mapped[list[FindingEvidence]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "entity_type", "value_normalized", name="uq_entity_case_type_value"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value_original: Mapped[str] = mapped_column(String(512), nullable=False)
    value_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    normalization_method: Mapped[str] = mapped_column(String(64), default="raw", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    event_links: Mapped[list[EventEntity]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EventEntity(Base):
    __tablename__ = "event_entities"

    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[str] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(64), primary_key=True, default="mentioned")
    raw_value: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    event: Mapped[Event] = relationship(back_populates="entity_links")
    entity: Mapped[Entity] = relationship(back_populates="event_links")
