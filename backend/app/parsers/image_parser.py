from __future__ import annotations

import re
import shutil
from io import BytesIO
from pathlib import Path

from ..config import get_settings
from ..utils.extraction import UTR_RE, extract_entities
from ..utils.geo import format_gps_point, parse_coordinates
from ..utils.timestamps import parse_flexible_timestamp
from .base import (
    BaseParser,
    CanonicalEventDraft,
    EntityDraft,
    ParseResult,
    ParseWarning,
    ParserContext,
)

try:
    from PIL import ExifTags, Image, ImageChops
except ImportError:  # pragma: no cover - optional dependency
    ExifTags = None
    Image = None
    ImageChops = None

try:
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None
    Output = None


def _ocr_lines(image) -> list[dict]:
    if pytesseract is None or Output is None:
        return []
    settings = get_settings()
    if settings.tesseract_cmd and not shutil.which(settings.tesseract_cmd):
        return []
    if not settings.tesseract_cmd and not shutil.which("tesseract"):
        return []
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    grouped: dict[tuple[int, int, int], dict] = {}
    for index, text in enumerate(data.get("text", [])):
        word = (text or "").strip()
        if not word:
            continue
        try:
            confidence = float(data["conf"][index])
        except (ValueError, TypeError):
            confidence = -1
        if confidence < 0:
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        left = int(data["left"][index])
        top = int(data["top"][index])
        width = int(data["width"][index])
        height = int(data["height"][index])
        entry = grouped.setdefault(
            key,
            {
                "words": [],
                "confidences": [],
                "left": left,
                "top": top,
                "right": left + width,
                "bottom": top + height,
            },
        )
        entry["words"].append(word)
        entry["confidences"].append(confidence)
        entry["left"] = min(entry["left"], left)
        entry["top"] = min(entry["top"], top)
        entry["right"] = max(entry["right"], left + width)
        entry["bottom"] = max(entry["bottom"], top + height)

    lines = []
    for key in sorted(grouped):
        entry = grouped[key]
        lines.append(
            {
                "text": " ".join(entry["words"]),
                "confidence": round(
                    sum(entry["confidences"]) / max(1, len(entry["confidences"])), 2
                ),
                "bbox": [
                    entry["left"],
                    entry["top"],
                    entry["right"] - entry["left"],
                    entry["bottom"] - entry["top"],
                ],
            }
        )
    return lines


def _exif_metadata(image) -> dict:
    if ExifTags is None:
        return {}
    try:
        exif = image.getexif()
    except Exception:
        return {}
    return {
        ExifTags.TAGS.get(tag, str(tag)): str(value)
        for tag, value in exif.items()
    }


def _exif_gps(image) -> tuple[float, float] | None:
    if ExifTags is None:
        return None
    try:
        exif = image.getexif()
        gps_info = exif.get_ifd(ExifTags.IFD.GPSInfo)
    except Exception:
        return None
    if not gps_info:
        return None

    def _number(value) -> float:
        try:
            if isinstance(value, tuple) and len(value) == 2:
                return float(value[0]) / float(value[1])
            return float(value)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    def _dms(values) -> float | None:
        if not values or len(values) < 3:
            return None
        degrees, minutes, seconds = (_number(value) for value in values[:3])
        return degrees + minutes / 60.0 + seconds / 3600.0

    latitude = _dms(gps_info.get(2))
    longitude = _dms(gps_info.get(4))
    if latitude is None or longitude is None:
        return None
    if str(gps_info.get(1, "N")).upper().startswith("S"):
        latitude = -latitude
    if str(gps_info.get(3, "E")).upper().startswith("W"):
        longitude = -longitude
    return parse_coordinates(latitude, longitude)


_TIMESTAMP_TEXT_RE = re.compile(
    r"\b(?:"
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?"
    r")\b"
)


def _parse_timestamp_text(raw: str, context: ParserContext):
    normalized = raw.replace(":", "-", 2) if re.match(r"^\d{4}:\d{2}:\d{2}", raw) else raw
    return parse_flexible_timestamp(
        normalized,
        default_timezone=context.timezone,
        reference_date=context.reference_date,
        default_year=context.default_year,
    )


def _ocr_timestamp(lines: list[dict], context: ParserContext):
    for line in lines:
        match = _TIMESTAMP_TEXT_RE.search(line.get("text", ""))
        if match:
            raw = match.group(0)
            return raw, _parse_timestamp_text(raw, context)
    return None, None


def _exif_timestamp(exif: dict, context: ParserContext):
    raw = next(
        (
            str(exif.get(key))
            for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime")
            if exif.get(key)
        ),
        None,
    )
    if not raw or raw == "None":
        return None, None
    return raw, _parse_timestamp_text(raw, context)


def _ela(image) -> dict:
    if Image is None or ImageChops is None:
        return {"available": False, "reason": "Pillow is not installed."}
    if image.format and image.format.upper() not in {"JPEG", "JPG"}:
        return {
            "available": False,
            "reason": (
                f"ELA is intended for lossy JPEG images; skipped for {image.format}. "
                "This is not evidence of manipulation."
            ),
        }
    try:
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        resaved = Image.open(buffer).convert("RGB")
        difference = ImageChops.difference(image.convert("RGB"), resaved)
        grayscale = difference.convert("L")
        pixels = list(grayscale.getdata())
        mean = sum(pixels) / max(1, len(pixels))
        maximum = max(pixels) if pixels else 0
        return {
            "available": True,
            "mean_difference": round(mean, 2),
            "max_difference": maximum,
            "note": "Compression anomaly indicator only; requires expert review.",
        }
    except Exception as error:  # noqa: BLE001 - optional analysis must not break parsing
        return {"available": False, "reason": str(error)}


class ImageParser(BaseParser):
    name = "image"
    version = "1.0.0"
    supported_extensions = (".png", ".jpg", ".jpeg")

    def parse(self, path: Path, context: ParserContext) -> ParseResult:
        warnings: list[ParseWarning] = []
        if Image is None:
            return ParseResult(
                parser_name=self.name,
                parser_version=self.version,
                events=[],
                warnings=[
                    ParseWarning(
                        source_locator="image:1",
                        message="Pillow is not installed; image analysis is unavailable.",
                    )
                ],
                metadata={"ocr_available": False, "pillow_available": False},
            )

        image = Image.open(path)
        image.load()
        exif = _exif_metadata(image)
        gps = _exif_gps(image)
        lines = _ocr_lines(image)
        ocr_available = bool(lines)
        timestamp_raw, timestamp = _ocr_timestamp(lines, context)
        if timestamp_raw is None:
            timestamp_raw, timestamp = _exif_timestamp(exif, context)
        if timestamp_raw is None:
            warnings.append(
                ParseWarning(
                    source_locator="image:1",
                    message=(
                        "No OCR or EXIF timestamp was found; image events are "
                        "reported without a normalized time."
                    ),
                )
            )
        if not ocr_available:
            warnings.append(
                ParseWarning(
                    source_locator="image:1",
                    message=(
                        "OCR text was not extracted. Tesseract may be unavailable, "
                        "or the image may contain no readable text."
                    ),
                )
            )

        events: list[CanonicalEventDraft] = []
        for index, line in enumerate(lines, start=1):
            text = line["text"]
            entities = [
                EntityDraft(entity_type, value, role, value)
                for entity_type, value, role in extract_entities(text)
            ]
            attributes = {
                "ocr_text": text,
                "ocr_confidence": line["confidence"],
                "bbox": line["bbox"],
                "image_format": image.format,
                "image_size": list(image.size),
                "exif": exif,
                "exif_gps": list(gps) if gps else None,
                "analysis_note": (
                    "OCR and image metadata are investigative indicators, "
                    "not proof of authenticity or manipulation."
                ),
            }
            if gps:
                point = format_gps_point(*gps)
                entities.append(EntityDraft("gps_point", point, "image_location", point))
                attributes["latitude"] = gps[0]
                attributes["longitude"] = gps[1]
                attributes["coordinate_source"] = "exif_gps"
            events.append(
                CanonicalEventDraft(
                    event_type="image_ocr",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized if timestamp else None,
                    timestamp_confidence=timestamp.confidence if timestamp else "unknown",
                    timestamp_timezone=timestamp.timezone_name if timestamp else None,
                    source_locator=f"bbox:{','.join(str(value) for value in line['bbox'])}",
                    source_snippet=text[:2000],
                    attributes=attributes,
                    entities=entities,
                )
            )

        if not lines and gps:
            point = format_gps_point(*gps)
            events.append(
                CanonicalEventDraft(
                    event_type="image_metadata",
                    timestamp_raw=timestamp_raw,
                    timestamp_normalized=timestamp.normalized if timestamp else None,
                    timestamp_confidence=timestamp.confidence if timestamp else "unknown",
                    timestamp_timezone=timestamp.timezone_name if timestamp else None,
                    source_locator="exif:gps",
                    source_snippet=f"EXIF GPS {point}",
                    attributes={
                        "latitude": gps[0],
                        "longitude": gps[1],
                        "coordinate_source": "exif_gps",
                        "exif_gps": list(gps),
                        "analysis_note": (
                            "EXIF GPS is a documented image metadata observation; "
                            "it does not establish who took the image."
                        ),
                    },
                    entities=[
                        EntityDraft("gps_point", point, "image_location", point)
                    ],
                )
            )

        return ParseResult(
            parser_name=self.name,
            parser_version=self.version,
            events=events,
            warnings=warnings,
            metadata={
                "ocr_available": ocr_available,
                "ocr_lines": len(lines),
                "exif": exif,
                "exif_gps": list(gps) if gps else None,
                "timestamp_raw": timestamp_raw,
                "image_size": list(image.size),
                "image_format": image.format,
                "ela": _ela(image),
            },
        )
