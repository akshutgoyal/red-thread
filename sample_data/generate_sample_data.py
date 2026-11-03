#!/usr/bin/env python3
"""Generate clearly labelled synthetic demo evidence for Red Thread.

This script creates the Operation PhishTrace scenario and a benign control
case. Every file is synthetic. It is not real evidence and must not be
presented as real source material.

The generated files intentionally preserve the source locators used in the
supplied solution package (for example, chat line 12 and 14, transaction row
19, and authentication line 412). The auth log is padded with blank lines so
those locators remain stable.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
OPERATION = ROOT / "operation_phishtrace"
BENIGN = ROOT / "benign_control"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def make_invoice(
    path: Path,
    *,
    invoice_id: str,
    payee: str,
    subtotal: str,
    cgst: str | None,
    sgst: str | None,
    gst: str | None,
    total: str,
    description: str,
) -> None:
    document = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    document.setFillColorRGB(0.06, 0.09, 0.16)
    document.rect(0, height - 90, width, 90, fill=1, stroke=0)
    document.setFillColorRGB(1, 1, 1)
    document.setFont("Helvetica-Bold", 24)
    document.drawString(54, height - 55, "SYNTHETIC DEMO INVOICE")
    document.setFont("Helvetica", 9)
    document.drawString(54, height - 72, "Generated for Red Thread evaluation - not real evidence")

    document.setFillColorRGB(0.06, 0.09, 0.16)
    document.setFont("Helvetica-Bold", 16)
    document.drawString(54, height - 135, "INVOICE")
    document.setFont("Helvetica", 11)
    document.drawString(54, height - 165, f"Invoice Number: {invoice_id}")
    document.drawString(54, height - 185, "Date: 15-Oct-2026")
    document.drawString(54, height - 205, "Billed To: Synthetic Victim")
    document.drawString(54, height - 225, "Description: " + description)

    document.setFont("Helvetica-Bold", 11)
    document.drawString(54, height - 270, "Description")
    document.drawString(350, height - 270, "Amount")
    document.setFont("Helvetica", 11)
    document.drawString(54, height - 295, description)
    document.drawString(350, height - 295, f"INR {subtotal}")

    y = height - 340
    document.drawString(54, y, "Subtotal")
    document.drawString(350, y, f"INR {subtotal}")
    y -= 24
    if cgst is not None:
        document.drawString(54, y, "CGST (9%)")
        document.drawString(350, y, f"INR {cgst}")
        y -= 24
    if sgst is not None:
        document.drawString(54, y, "SGST (9%)")
        document.drawString(350, y, f"INR {sgst}")
        y -= 24
    if gst is not None:
        document.drawString(54, y, "GST")
        document.drawString(350, y, f"INR {gst}")
        y -= 24
    document.setFont("Helvetica-Bold", 12)
    document.drawString(54, y, "Total Due")
    document.drawString(350, y, f"INR {total}")
    y -= 40
    document.setFont("Helvetica", 11)
    document.drawString(54, y, f"Pay to VPA: {payee}")
    y -= 22
    document.drawString(54, y, f"UPI ID: {payee}")
    y -= 22
    document.drawString(54, y, "Payment Reference: 312456789012")

    document.setFont("Helvetica", 8)
    document.setFillColorRGB(0.4, 0.45, 0.55)
    document.drawString(54, 50, "SYNTHETIC DATA - created for the Red Thread demonstration. Not real evidence.")
    document.save()


def make_screenshot(path: Path) -> None:
    image = Image.new("RGB", (1080, 2160), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = find_font(54)
    big_font = find_font(92)
    body_font = find_font(42)
    small_font = find_font(30)

    draw.rectangle([0, 0, 1080, 140], fill="#0f172a")
    draw.text((54, 48), "Red Thread SYNTHETIC DEMO", font=body_font, fill="#f8fafc")
    draw.text((54, 1080), "Payment Successful", font=title_font, fill="#166534")
    draw.ellipse([54, 900, 174, 1020], fill="#22c55e")
    draw.line([90, 960, 112, 984, 145, 936], fill="#ffffff", width=12)

    draw.text((54, 1160), "INR 4,500.00", font=big_font, fill="#0f172a")
    draw.text((54, 1320), "To: gov-security@upi", font=body_font, fill="#334155")
    draw.text((54, 1400), "UTR: 312456789012", font=body_font, fill="#334155")
    draw.text((54, 1480), "Date: 15 Oct 2026, 11:05 AM", font=small_font, fill="#64748b")
    draw.rounded_rectangle([54, 1600, 1026, 1780], radius=24, outline="#cbd5e1", width=3)
    draw.text((84, 1640), "Payment ID: PAY-2026-9912", font=small_font, fill="#475569")
    draw.text((84, 1700), "Status: SUCCESS", font=small_font, fill="#166534")
    draw.text((54, 2040), "SYNTHETIC IMAGE - not a real payment screenshot.", font=small_font, fill="#94a3b8")
    image.save(path, format="PNG")


def build_operation() -> None:
    OPERATION.mkdir(parents=True, exist_ok=True)

    write_csv(
        OPERATION / "call_log.csv",
        [
            "timestamp_raw",
            "caller_id",
            "receiver_id",
            "call_type",
            "duration_sec",
            "cell_tower_id",
        ],
        [
            ["2026-10-15 09:40:00 IST", "+91-99887-76655", "+91-91234-56789", "INCOMING", "35", "DEL-NORTH-01"],
            ["2026-10-15 10:00:12 IST", "+91-91234-56789", "+91-99887-76655", "OUTGOING", "18", "DEL-NORTH-02"],
            ["2026-10-15 10:15:00 IST", "+91-98765-43210", "+91-91234-56789", "INCOMING", "142", "DEL-NORTH-04"],
            ["2026-10-15 10:16:30 IST", "+91-98765-43210", "+91-91234-56789", "MISSED", "0", "DEL-NORTH-04"],
            ["2026-10-15 10:30:00 IST", "+91-91234-56789", "+91-98765-43210", "OUTGOING", "22", "DEL-NORTH-04"],
            ["2026-10-15 12:00:00 IST", "+91-91234-56789", "+91-90000-11111", "INCOMING", "61", "DEL-SOUTH-02"],
        ],
    )

    chat_lines = [
        "[2026-10-15, 09:00:00 IST] +91-91234-56789: Good morning. Did you receive the vendor list?",
        "[2026-10-15, 09:02:10 IST] +91-99887-76655: Yes, reviewing it now.",
        "[2026-10-15, 09:05:00 IST] +91-91234-56789: Please keep the invoice copy ready.",
        "[2026-10-15, 09:10:00 IST] +91-99887-76655: Sure.",
        "[2026-10-15, 09:20:00 IST] +91-91234-56789: The audit team may call today.",
        "[2026-10-15, 09:30:00 IST] +91-99887-76655: I will keep my phone nearby.",
        "[2026-10-15, 09:45:00 IST] +91-91234-56789: Thanks.",
        "[2026-10-15, 10:00:00 IST] +91-91234-56789: Any update?",
        "[2026-10-15, 10:05:00 IST] +91-99887-76655: Still waiting.",
        "[2026-10-15, 10:10:00 IST] +91-91234-56789: Please stay available.",
        "[2026-10-15, 10:16:00 IST] +91-98765-43210: Hello, this is the cyber compliance desk.",
        "[2026-10-15, 10:18:30 IST] +91-98765-43210: Turant INR 45,000 bhejo warna account block ho jayega. Government security verification ke liye.",
        "[2026-10-15, 10:20:00 IST] +91-91234-56789: Is this official? Please share a reference.",
        "[2026-10-15, 10:24:15 IST] +91-98765-43210: <attached: invoice_45000.pdf> Invoice bhej diya. Jaldi pay karo. gov-security@upi par transfer karo.",
        "[2026-10-15, 10:26:00 IST] +91-98765-43210: Reference UTR 312456789012 use karna.",
        "[2026-10-15, 10:30:00 IST] +91-91234-56789: I am checking with my bank.",
        "[2026-10-15, 10:45:00 IST] +91-98765-43210: Delay mat karo. Case file open ho jayegi.",
        "[2026-10-15, 11:05:00 IST] +91-91234-56789: Payment done. Please confirm.",
        "[2026-10-15, 11:20:00 IST] +91-98765-43210: Received. Thank you.",
        "[2026-10-15, 14:00:00 IST] +91-91234-56789: I will report this to the bank.",
    ]
    write_lines(OPERATION / "chat_export.txt", chat_lines)

    make_invoice(
        OPERATION / "invoice_45000.pdf",
        invoice_id="INV-2026-9912",
        payee="gov-security@upi",
        subtotal="45,000.00",
        cgst=None,
        sgst=None,
        gst="0.00",
        total="45,000.00",
        description="Cyber Security Compliance Fee",
    )
    make_screenshot(OPERATION / "payment_screenshot.png")

    upi_rows: list[list[str]] = []
    for index in range(1, 18):
        upi_rows.append(
            [
                f"TXN-BEN-{1000 + index}",
                f"3124567800{index:02d}",
                f"2026-10-{10 + (index % 5):02d} {8 + (index % 9):02d}:15:00",
                "victim@okhdfc",
                ["grocery-store@okicici", "electricity-board@okaxis", "mobile-recharge@okhdfc"][index % 3],
                f"{500 + index * 37}.00",
                "INR",
                "SUCCESS",
            ]
        )
    upi_rows.append(
        [
            "TXN-101982",
            "312456789012",
            "2026-10-15 11:05:00",
            "victim@okhdfc",
            "fraud-mule@okaxis",
            "45000.00",
            "INR",
            "SUCCESS",
        ]
    )
    upi_rows.append(
        [
            "TXN-101983",
            "312456789013",
            "2026-10-15 11:20:00",
            "victim@okhdfc",
            "grocery-store@okicici",
            "1250.00",
            "INR",
            "SUCCESS",
        ]
    )
    write_csv(
        OPERATION / "upi_transaction_log.csv",
        [
            "txn_id",
            "utr_number",
            "timestamp_ist",
            "payer_vpa",
            "payee_vpa",
            "amount_inr",
            "currency",
            "status",
        ],
        upi_rows,
    )

    auth_lines = [""] * 369
    burst = [
        ("05:45:01", "1001", "alice"),
        ("05:45:06", "1002", "bob"),
        ("05:45:11", "1003", "carol"),
        ("05:45:16", "1004", "dave"),
        ("05:45:21", "1005", "erin"),
        ("05:45:26", "1006", "frank"),
        ("05:45:31", "1007", "grace"),
        ("05:45:36", "1008", "hank"),
        ("05:50:00", "1009", "root"),
        ("05:52:00", "1010", "admin"),
    ]
    for index, (timestamp, pid, user) in enumerate(burst):
        auth_lines.append(
            f"Oct 15 {timestamp} srv sshd[{pid}]: Failed password for invalid user {user} "
            f"from 203.0.113.45 port {40001 + index} ssh2"
        )
    while len(auth_lines) < 411:
        auth_lines.append("")
    auth_lines.append(
        "Oct 15 06:00:00 srv sshd[4112]: Accepted publickey for admin from 103.21.244.2 "
        "port 51244 ssh2: RSA SHA256:d8a1f4c2e9b7"
    )
    auth_lines.append(
        "Oct 15 06:00:05 srv sshd[4112]: pam_unix(sshd:session): session opened for user admin by (uid=0)"
    )
    auth_lines.append(
        "Oct 15 06:02:00 srv sudo: admin : TTY=pts/0 ; PWD=/home/admin ; USER=root ; "
        "COMMAND=/usr/bin/apt update"
    )
    auth_lines.append(
        "Oct 15 06:05:00 srv sshd[4112]: pam_unix(sshd:session): session closed for user admin"
    )
    auth_lines.append(
        "Oct 15 06:06:00 srv sshd[4200]: Failed password for invalid user ipv6test "
        "from 2001:db8::1 port 50000 ssh2"
    )
    write_lines(OPERATION / "auth.log", auth_lines)


def build_benign() -> None:
    BENIGN.mkdir(parents=True, exist_ok=True)
    make_invoice(
        BENIGN / "invoice_legit.pdf",
        invoice_id="INV-2026-9913",
        payee="vendor-support@icici",
        subtotal="45,000.00",
        cgst="4,050.00",
        sgst="4,050.00",
        gst=None,
        total="53,100.00",
        description="Annual security audit subscription",
    )
    write_csv(
        BENIGN / "upi_statement.csv",
        [
            "txn_id",
            "utr_number",
            "timestamp_ist",
            "payer_vpa",
            "payee_vpa",
            "amount_inr",
            "currency",
            "status",
        ],
        [
            [
                "TXN-200001",
                "412456789099",
                "2026-10-16 14:30:00",
                "victim@okhdfc",
                "vendor-support@icici",
                "53100.00",
                "INR",
                "SUCCESS",
            ],
            [
                "TXN-200002",
                "412456789100",
                "2026-10-16 15:00:00",
                "victim@okhdfc",
                "grocery-store@okicici",
                "2100.00",
                "INR",
                "SUCCESS",
            ],
        ],
    )


def main() -> None:
    build_operation()
    build_benign()

    manifest: dict[str, str] = {}
    for path in sorted([*OPERATION.glob("*"), *BENIGN.glob("*")]):
        if path.is_file() and path.name != "README.md":
            manifest[str(path.relative_to(ROOT))] = sha256(path)
    (ROOT / "manifest.json").write_text(
        json.dumps(
            {
                "warning": "SYNTHETIC DEMO DATA. Not real evidence.",
                "files": manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated synthetic demo data under {ROOT}")
    for name, digest in manifest.items():
        print(f"  {name}  {digest}")


if __name__ == "__main__":
    main()
