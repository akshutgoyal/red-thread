from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import TimestampMixin, new_id

if TYPE_CHECKING:
    from .audit import AuditEvent
    from .evidence import Evidence
    from .event import Event
    from .finding import Finding
    from .report import Report


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    investigator_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
