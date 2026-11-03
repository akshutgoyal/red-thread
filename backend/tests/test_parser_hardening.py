from __future__ import annotations

from datetime import datetime, timezone

from app.parsers.base import ParseWarning, ParserContext
from app.parsers.image_parser import _exif_gps, _ocr_timestamp
from app.parsers.registry import detect_parser
from app.services.investigation_service import warning_messages


def _context() -> ParserContext:
    return ParserContext(
        case_id="case",
        evidence_id="evidence",
        source_filename="image.png",
        reference_date=datetime(2026, 10, 20, tzinfo=timezone.utc),
        timezone="UTC",
    )


def test_filename_hint_does_not_override_csv_structure(tmp_path):
    path = tmp_path / "auth_call.csv"
    path.write_text(
        "timestamp_raw,caller_id,receiver_id,call_type,duration_sec\n"
        "2026-10-14 19:00:00 IST,+919900112233,+919900445566,OUTGOING,42\n",
        encoding="utf-8",
    )

    parser = detect_parser(path)
    assert parser is not None
    assert parser.name == "call_log"


def test_parser_warning_messages_report_truncation():
    warnings = [
        ParseWarning(source_locator=f"line:{index}", message=f"warning {index}")
        for index in range(55)
    ]

    messages = warning_messages(warnings)
    assert len(messages) == 51
    assert messages[0] == "warning 0"
    assert "5 additional parser warning(s) omitted" in messages[-1]


def test_ocr_timestamp_is_normalized_from_text():
    raw, parsed = _ocr_timestamp(
        [{"text": "Captured 2026-10-14 19:05:00 UTC", "confidence": 98, "bbox": [0, 0, 1, 1]}],
        _context(),
    )

    assert raw == "2026-10-14 19:05:00"
    assert parsed is not None
    assert parsed.normalized is not None
    assert parsed.normalized.hour == 19


def test_exif_gps_is_extracted_with_hemispheres():
    class FakeExif:
        def get_ifd(self, _tag):
            return {
                1: "N",
                2: ((12, 1), (58, 1), (18, 1)),
                3: "E",
                4: ((77, 1), (35, 1), (40, 1)),
            }

    class FakeImage:
        def getexif(self):
            return FakeExif()

    coordinates = _exif_gps(FakeImage())
    assert coordinates is not None
    latitude, longitude = coordinates
    assert round(latitude, 4) == round(12 + 58 / 60 + 18 / 3600, 4)
    assert round(longitude, 4) == round(77 + 35 / 60 + 40 / 3600, 4)
