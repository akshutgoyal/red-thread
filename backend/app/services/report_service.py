from __future__ import annotations

import json
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import AiQuery, AuditEvent, Case, Event, Evidence, Finding, GraphEdge, Report
from ..models.base import new_id
from . import audit_service, storage_service

DISCLAIMER = (
    "DRAFT - This report is prepared for human review. It is not automatically "
    "court-admissible and does not establish guilt, fraud, authenticity or intent. "
    "Any Section 63 Bharatiya Sakshya Adhiniyam certificate must be reviewed, completed "
    "and signed by the appropriate authorized person. Red Thread does not sign or attest on "
    "behalf of an investigator."
)


def _safe(text: Any) -> str:
    value = str(text if text is not None else "")
    replacements = {
        "\u20b9": "INR ",
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value.encode("latin-1", "replace").decode("latin-1")


def _paragraph(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe(text).replace("\n", "<br/>"), style)


def _table(
    rows: list[list[Any]],
    col_widths: list[float],
    *,
    header: bool = True,
    font_size: float = 7.5,
) -> Table:
    table = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _load_report_data(db: Session, case: Case) -> dict[str, Any]:
    evidence = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.case_id == case.id)
            .order_by(Evidence.uploaded_at.asc())
        )
    )
    events = list(
        db.scalars(
            select(Event)
            .where(Event.case_id == case.id)
            .order_by(Event.timestamp_normalized.is_(None), Event.timestamp_normalized.asc())
            .limit(2000)
        )
    )
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.case_id == case.id)
            .options(selectinload(Finding.evidence_links))
            .order_by(Finding.created_at.asc())
        )
    )
    audit = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.case_id == case.id)
            .order_by(AuditEvent.created_at.asc())
            .limit(500)
        )
    )
    ai_queries = list(
        db.scalars(
            select(AiQuery)
            .where(AiQuery.case_id == case.id)
            .order_by(AiQuery.created_at.asc())
            .limit(100)
        )
    )
    graph_edges = list(db.scalars(select(GraphEdge).where(GraphEdge.case_id == case.id)))

    return {
        "case": {
            "id": case.id,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "investigator_notes": case.investigator_notes,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
        "evidence": [
            {
                "id": item.id,
                "filename": item.original_filename,
                "media_type": item.media_type,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
                "uploaded_at": item.uploaded_at.isoformat(),
                "processing_status": item.processing_status,
                "parser": item.parser_name,
                "parser_version": item.parser_version,
                "hash_verified": item.hash_verified,
                "hash_verified_at": (
                    item.hash_verified_at.isoformat() if item.hash_verified_at else None
                ),
                "processing_error": item.processing_error,
            }
            for item in evidence
        ],
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "timestamp_raw": event.timestamp_raw,
                "timestamp_normalized": (
                    event.timestamp_normalized.isoformat()
                    if event.timestamp_normalized
                    else None
                ),
                "timestamp_confidence": event.timestamp_confidence,
                "source_filename": event.source_filename,
                "source_locator": event.source_locator,
                "evidence_id": event.evidence_id,
                "attributes": event.attributes_json,
                "warnings": event.warnings_json,
            }
            for event in events
        ],
        "findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "category": finding.category,
                "title": finding.title,
                "explanation": finding.explanation,
                "detection_method": finding.detection_method,
                "confidence": finding.confidence,
                "status": finding.status,
                "limitations": finding.limitations,
                "alternative_explanations": finding.alternative_explanations,
                "reviewer_note": finding.reviewer_note,
                "reviewed_at": (
                    finding.reviewed_at.isoformat() if finding.reviewed_at else None
                ),
                "evidence_links": [
                    {
                        "evidence_id": link.evidence_id,
                        "event_id": link.event_id,
                        "role": link.role,
                        "source_locator": link.source_locator,
                    }
                    for link in finding.evidence_links
                ],
            }
            for finding in findings
        ],
        "graph": {
            "edge_count": len(graph_edges),
            "by_type": dict(Counter(edge.edge_type for edge in graph_edges)),
            "edges": [
                {
                    "id": edge.id,
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "edge_type": edge.edge_type,
                    "match_method": edge.match_method,
                    "confidence": edge.confidence,
                    "explanation": edge.explanation,
                }
                for edge in graph_edges[:200]
            ],
        },
        "audit": [
            {
                "id": item.id,
                "action": item.action,
                "actor": item.actor,
                "evidence_id": item.evidence_id,
                "details": item.details_json,
                "created_at": item.created_at.isoformat(),
            }
            for item in audit
        ],
        "ai_queries": [
            {
                "id": query.id,
                "question": query.question,
                "answer": query.answer,
                "provider": query.provider,
                "model": query.model,
                "validation_status": query.validation_status,
                "citations": query.citations_json,
                "latency_ms": query.latency_ms,
                "created_at": query.created_at.isoformat(),
                "ai_generated": True,
            }
            for query in ai_queries
        ],
        "limitations": [
            "SHA-256 verification proves stored-file correspondence, not pre-acquisition authenticity.",
            "Threshold-based alerts are indicators, not proof of compromise.",
            "OCR, EXIF and compression analysis can produce false positives.",
            "Heuristic temporal proximity is a lead, not a relationship.",
            "AI-generated text is an interpretation and may be wrong.",
            DISCLAIMER,
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_pdf(path: Path, data: dict[str, Any]) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RakshaTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "RakshaSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "RakshaSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "RakshaBody",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    small_style = ParagraphStyle(
        "RakshaSmall",
        parent=body_style,
        fontSize=7.2,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    warning_style = ParagraphStyle(
        "RakshaWarning",
        parent=body_style,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#9a3412"),
        backColor=colors.HexColor("#fff7ed"),
        borderColor=colors.HexColor("#fdba74"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    )
    mono_style = ParagraphStyle(
        "RakshaMono",
        parent=small_style,
        fontName="Courier",
        fontSize=6.5,
        leading=8.5,
    )

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Red Thread Investigation Report - {data['case']['title']}",
        author="Red Thread",
    )
    story: list[Any] = []
    case = data["case"]

    story.append(_paragraph("Red Thread Investigation Report", title_style))
    story.append(
        _paragraph(
            "From fragmented digital traces to an explainable, human-reviewed investigation picture",
            subtitle_style,
        )
    )
    story.append(
        _paragraph(
            "DRAFT - HUMAN REVIEW REQUIRED. Not automatically court-admissible.",
            warning_style,
        )
    )
    story.append(Spacer(1, 4))

    case_rows = [
        ["Case title", _safe(case["title"])],
        ["Case ID", _safe(case["id"])],
        ["Status", _safe(case["status"])],
        ["Created", _safe(case["created_at"])],
        ["Report generated", _safe(data["generated_at"])],
        ["Description", _safe(case["description"] or "-")],
        ["Investigator notes", _safe(case["investigator_notes"] or "-")],
    ]
    story.append(_table(case_rows, [38 * mm, 140 * mm], header=False, font_size=8))
    story.append(Spacer(1, 8))

    story.append(_paragraph("1. Evidence inventory", section_style))
    evidence_rows: list[list[Any]] = [
        ["File", "Size", "SHA-256", "Status", "Integrity"]
    ]
    for item in data["evidence"]:
        evidence_rows.append(
            [
                _paragraph(item["filename"], small_style),
                _paragraph(f"{item['size_bytes']} B", small_style),
                _paragraph(item["sha256"], mono_style),
                _paragraph(item["processing_status"], small_style),
                _paragraph(
                    "verified" if item["hash_verified"] else "not checked", small_style
                ),
            ]
        )
    if len(evidence_rows) == 1:
        evidence_rows.append(["No evidence", "-", "-", "-", "-"])
    story.append(
        _table(
            evidence_rows,
            [43 * mm, 16 * mm, 72 * mm, 23 * mm, 24 * mm],
            font_size=7,
        )
    )
    if len(data["evidence"]) > 60:
        story.append(_paragraph("Inventory truncated for this PDF; see JSON report.", small_style))

    story.append(_paragraph("2. Integrity verification summary", section_style))
    verified = sum(1 for item in data["evidence"] if item["hash_verified"])
    story.append(
        _paragraph(
            f"{verified} of {len(data['evidence'])} evidence records have a successful "
            "SHA-256 verification recorded in this case. Hash verification demonstrates "
            "that the stored bytes match the digest recorded at intake; it does not by "
            "itself establish pre-acquisition authenticity.",
            body_style,
        )
    )

    story.append(_paragraph("3. Timeline events", section_style))
    event_rows: list[list[Any]] = [["Time (UTC)", "Event", "Source", "Confidence"]]
    for event in data["events"][:180]:
        event_rows.append(
            [
                _paragraph(event["timestamp_normalized"] or "unknown", small_style),
                _paragraph(event["event_type"], small_style),
                _paragraph(
                    f"{event['source_filename']} / {event['source_locator']}", small_style
                ),
                _paragraph(event["timestamp_confidence"], small_style),
            ]
        )
    if len(event_rows) == 1:
        event_rows.append(["No events", "-", "-", "-"])
    story.append(
        _table(event_rows, [36 * mm, 42 * mm, 76 * mm, 24 * mm], font_size=7)
    )
    if len(data["events"]) > 180:
        story.append(
            _paragraph(
                f"Showing 180 of {len(data['events'])} events. The complete timeline is "
                "available in the JSON report.",
                small_style,
            )
        )

    story.append(_paragraph("4. Findings for human review", section_style))
    if not data["findings"]:
        story.append(_paragraph("No findings were recorded.", body_style))
    for index, finding in enumerate(data["findings"], start=1):
        block: list[Any] = []
        block.append(
            _paragraph(
                f"{index}. [{finding['severity'].upper()}] {finding['title']}",
                section_style,
            )
        )
        block.append(
            _paragraph(
                f"Detection: {finding['detection_method']} | Confidence: "
                f"{finding['confidence']} | Status: {finding['status']}",
                small_style,
            )
        )
        block.append(_paragraph(finding["explanation"] or "-", body_style))
        block.append(
            _paragraph(
                f"Limitations: {finding['limitations'] or 'None recorded.'}",
                small_style,
            )
        )
        block.append(
            _paragraph(
                "Alternative explanations: "
                f"{finding['alternative_explanations'] or 'None recorded.'}",
                small_style,
            )
        )
        if finding["reviewer_note"]:
            block.append(_paragraph(f"Reviewer note: {finding['reviewer_note']}", small_style))
        if finding["evidence_links"]:
            links = "; ".join(
                f"{link['evidence_id']}"
                + (f" / {link['event_id']}" if link["event_id"] else "")
                + (f" / {link['source_locator']}" if link["source_locator"] else "")
                for link in finding["evidence_links"]
            )
            block.append(_paragraph(f"Supporting records: {links}", mono_style))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 4))

    story.append(_paragraph("5. Relationship graph summary", section_style))
    story.append(
        _paragraph(
            f"{data['graph']['edge_count']} persisted relationship edge(s). "
            f"By type: {json.dumps(data['graph']['by_type'], default=str)}",
            body_style,
        )
    )
    if data["graph"]["edges"]:
        edge_rows: list[list[Any]] = [["Type", "Method", "Confidence", "Explanation"]]
        for edge in data["graph"]["edges"][:80]:
            edge_rows.append(
                [
                    _paragraph(edge["edge_type"], small_style),
                    _paragraph(edge["match_method"], small_style),
                    _paragraph(edge["confidence"], small_style),
                    _paragraph(edge["explanation"], small_style),
                ]
            )
        story.append(_table(edge_rows, [35 * mm, 30 * mm, 20 * mm, 93 * mm], font_size=6.5))
    story.append(
        _paragraph(
            "Only exact identifier matches and deterministic conflicts are direct "
            "relationships. Temporal or fuzzy links are investigative leads and are not "
            "proof of a connection.",
            small_style,
        )
    )

    story.append(_paragraph("6. AI-generated interpretations", section_style))
    story.append(
        _paragraph(
            "The following section contains AI-generated text. It is not evidence and may be "
            "incorrect. Every citation must be checked against the stored record.",
            warning_style,
        )
    )
    if not data["ai_queries"]:
        story.append(_paragraph("No AI queries were recorded for this case.", body_style))
    for query in data["ai_queries"]:
        block = [
            _paragraph(
                f"AI-GENERATED - {query['provider']} / {query['model']} "
                f"({query['validation_status']})",
                small_style,
            ),
            _paragraph(f"Question: {query['question']}", body_style),
            _paragraph(f"Answer: {query['answer']}", body_style),
            _paragraph(
                "Citations: "
                + json.dumps(query["citations"], ensure_ascii=False, default=str)[:1400],
                mono_style,
            ),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 4))

    story.append(_paragraph("7. Audit trail summary", section_style))
    audit_rows: list[list[Any]] = [["Time (UTC)", "Action", "Actor", "Evidence"]]
    for item in data["audit"][:120]:
        audit_rows.append(
            [
                _paragraph(item["created_at"], small_style),
                _paragraph(item["action"], small_style),
                _paragraph(item["actor"], small_style),
                _paragraph(item["evidence_id"] or "-", mono_style),
            ]
        )
    if len(audit_rows) == 1:
        audit_rows.append(["No audit events", "-", "-", "-"])
    story.append(_table(audit_rows, [38 * mm, 55 * mm, 30 * mm, 55 * mm], font_size=6.5))

    story.append(_paragraph("8. Limitations and legal caution", section_style))
    for limitation in data["limitations"]:
        story.append(_paragraph(f"- {limitation}", body_style))

    story.append(_paragraph("9. Section 63 BSA preparation - DRAFT ONLY", section_style))
    story.append(
        _paragraph(
            "This is a preparation template, not a signed certificate. It must be reviewed, "
            "completed and signed by the appropriate authorized person. No signature is "
            "fabricated or attested by Red Thread.",
            warning_style,
        )
    )
    story.append(
        _paragraph(
            "Part A - Technical particulars (draft): the case evidence inventory, stored "
            "SHA-256 digests, parser metadata, tool versions and integrity-verification "
            "results are recorded in this report. The authorized person must confirm that "
            "the described electronic record, the manner of its production, and the relevant "
            "device or process are correctly described.",
            body_style,
        )
    )
    story.append(
        _paragraph(
            "Part B - Signature block (to be completed by the authorized examiner):",
            body_style,
        )
    )
    signature_rows = [
        ["Name", ""],
        ["Designation / organization", ""],
        ["Signature", ""],
        ["Place", ""],
        ["Date", ""],
        ["Remarks", ""],
    ]
    story.append(_table(signature_rows, [50 * mm, 128 * mm], header=False, font_size=8))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(16 * mm, 8 * mm, "Red Thread - Draft for human review - not court-admissible")
        canvas.drawRightString(194 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)


def generate_report(
    db: Session,
    case_id: str,
    report_type: str,
) -> Report:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    report_type = report_type.lower()
    if report_type not in {"pdf", "json"}:
        raise HTTPException(status_code=422, detail="report_type must be pdf or json.")

    data = _load_report_data(db, case)
    report_id = new_id()
    extension = "pdf" if report_type == "pdf" else "json"
    filename = f"red-thread_report_{case_id[:8]}_{report_id[:8]}.{extension}"
    relative_path = storage_service.report_key(case_id, filename)
    media_type = "application/pdf" if report_type == "pdf" else "application/json"

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / filename
        if report_type == "pdf":
            _build_pdf(path, data)
        else:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        output = path.read_bytes()

    storage_service.save_bytes(relative_path, output, content_type=media_type)

    metadata = {
        "generated_at": data["generated_at"],
        "evidence_count": len(data["evidence"]),
        "event_count": len(data["events"]),
        "finding_count": len(data["findings"]),
        "ai_query_count": len(data["ai_queries"]),
        "graph_edge_count": data["graph"]["edge_count"],
        "disclaimer": DISCLAIMER,
    }
    report = Report(
        id=report_id,
        case_id=case_id,
        report_type=report_type,
        filename=filename,
        relative_path=relative_path,
        status="ready",
        metadata_json=metadata,
    )
    db.add(report)
    db.flush()
    audit_service.record(
        db,
        case_id,
        "report.generated",
        details={"report_id": report.id, "report_type": report_type, "filename": filename},
    )
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, case_id: str) -> list[Report]:
    return list(
        db.scalars(
            select(Report)
            .where(Report.case_id == case_id)
            .order_by(Report.generated_at.desc())
        )
    )


def get_report(db: Session, report_id: str, case_id: str) -> Report:
    report = db.get(Report, report_id)
    if report is None or report.case_id != case_id:
        raise HTTPException(status_code=404, detail="Report not found in this case.")
    return report
