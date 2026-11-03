# Operation PhishTrace — SYNTHETIC DEMO DATA

**This directory contains synthetic data created for the Red Thread demonstration. It is not real evidence, not a real payment, and not a real authentication log. Do not present it as source material from a real incident.**

## Scenario

A victim receives a call and a chat demand for `INR 45,000`, an invoice claiming the UPI ID
`gov-security@upi`, and a payment screenshot claiming only `INR 4,500` with UTR
`312456789012`. The bank/UPI ledger records the same UTR with `INR 45,000` paid to
`fraud-mule@okaxis`. A separate SSH authentication log contains a failed-login burst from
`203.0.113.45` and an accepted public-key login for `admin` from `103.21.244.2`.

## Files and intended source locators

| File | Purpose | Key locator |
|---|---|---|
| `call_log.csv` | Call records | the 10:15 call is spreadsheet row 4 (`row:4`) |
| `chat_export.txt` | Chat transcript | the demand is line 12; the invoice attachment is line 14 |
| `invoice_45000.pdf` | Text-based synthetic invoice | invoice `INV-2026-9912`, total `INR 45,000` |
| `payment_screenshot.png` | Generated synthetic screenshot | OCR text contains `INR 4,500.00` and UTR `312456789012` |
| `upi_transaction_log.csv` | UPI ledger | the target transaction is spreadsheet row 19 (`row:19`) |
| `auth.log` | Synthetic SSH log | accepted public-key login is line 412 |

The auth log is padded with blank lines before the key entries so that the documented line
412 locator remains stable. Blank lines are ignored by the parser.

## Expected Red Thread demonstration

1. Every file is hashed with SHA-256 at intake.
2. The invoice parser extracts the invoice ID, total and claimed VPA.
3. The transaction parser extracts UTR `312456789012`, amount `45,000` and payee
   `fraud-mule@okaxis`.
4. The screenshot OCR extracts the displayed amount `4,500`, the claimed VPA
   `gov-security@upi` and the UTR.
5. Reconciliation creates an exact UTR match, an amount-discrepancy finding and a payee
   mismatch finding. It does **not** declare fraud or guilt.
6. The authentication parser creates threshold-based indicators for the failed-login burst.
   The SSH events are not linked to the financial events merely because their timestamps are
   near each other.

## Benign control

`../benign_control/` contains a legitimate invoice and matching UPI statement. The invoice
subtotal is `45,000`, CGST and SGST are each `4,050` at 9%, and the total is `53,100`. The
statement records `53,100` to the same payee. Reconciliation should validate the arithmetic
and avoid a high/medium fraud indicator.

## Important limitations

- The screenshot is generated with Pillow, not captured from a real payment app.
- The PDF uses `INR` rather than the rupee glyph for font compatibility.
- OCR results depend on the installed Tesseract binary and can vary.
- The SSH timestamps omit a year. Red Thread records the inferred year and timezone assumption.
- `manifest.json` records the generated file hashes for convenience. Red Thread computes its own
  hashes during upload and never trusts the manifest as evidence.
