from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

from ..config import get_settings
from ..utils.extraction import UTR_RE, extract_entities
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
        lines = _ocr_lines(image)
        ocr_available = bool(lines)
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
            timestamp = parse_flexible_timestamp(
                None,
                default_timezone=context.timezone,
                reference_date=context.reference_date,
                default_year=context.default_year,
            )
            entities = [
                EntityDraft(entity_type, value, role, value)
                for entity_type, value, role in extract_entities(text)
            ]
            events.append(
                CanonicalEventDraft(
                    event_type="image_ocr",
                    timestamp_raw=None,
                    timestamp_normalized=timestamp.normalized,
                    timestamp_confidence="unknown",
                    timestamp_timezone=None,
                    source_locator=f"bbox:{','.join(str(value) for value in line['bbox'])}",
                    source_snippet=text[:2000],
                    attributes={
                        "ocr_text": text,
                        "ocr_confidence": line["confidence"],
                        "bbox": line["bbox"],
                        "image_format": image.format,
                        "image_size": list(image.size),
                        "exif": exif,
                        "analysis_note": (
                            "OCR and image metadata are investigative indicators, "
                            "not proof of authenticity or manipulation."
                        ),
                    },
                    entities=entities,
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
                "image_size": list(image.size),
                "image_format": image.format,
                "ela": _ela(image),
            },
        )
