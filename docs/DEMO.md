# Demo Walkthrough: Operation PhishTrace

**All demo files are synthetic. They were generated for Red Thread and are not real evidence.**

## Story

A victim receives a call from `+91-98765-43210` and a chat demand for `INR 45,000`. The sender
attaches an invoice (`INV-2026-9912`) claiming the UPI ID `gov-security@upi`. A payment
screenshot claims only `INR 4,500` with UTR `312456789012`. The UPI ledger records the same UTR
with `INR 45,000` paid to `fraud-mule@okaxis`. A separate authentication log contains a
failed-login burst and an accepted public-key login for `admin`.

## Files and locators

| File | Locator | Purpose |
|---|---|---|
| `call_log.csv` | row 4 | 10:15 call from `+91-98765-43210` |
| `chat_export.txt` | line 12 | demand for `INR 45,000` |
| `chat_export.txt` | line 14 | `<attached: invoice_45000.pdf>` |
| `invoice_45000.pdf` | page 1 | invoice total, claimed VPA |
| `payment_screenshot.png` | OCR | `INR 4,500.00`, `gov-security@upi`, UTR |
| `upi_transaction_log.csv` | row 19 | `45,000`, `fraud-mule@okaxis`, same UTR |
| `auth.log` | line 412 | accepted public-key login from `103.21.244.2` |

The auth log is padded with blank lines so the documented line 412 remains stable.

## Running the demo

1. Start the backend and frontend.
2. Generate the files:

   ```bash
   backend/.venv/bin/python sample_data/generate_sample_data.py
   ```

3. Seed through the API:

   ```bash
   backend/.venv/bin/python scripts/seed_demo.py --include-benign
   ```

4. Open the printed case URL, or select the case in the UI.

Alternatively, use the UI:

1. Create a case.
2. Open **Evidence intake**.
3. Upload the six files from `sample_data/operation_phishtrace/`.
4. Keep **Parse after upload** enabled.
5. Open **Evidence vault** and verify the hashes.
6. Open **Auth analysis**, **Timeline**, **Relationship graph**, and **Findings**.
7. Generate a PDF or JSON report.

## Expected findings

### Exact UTR match (informational)

The screenshot OCR and the transaction ledger both contain `312456789012`. The graph shows an
`exact_utr_match` edge. This proves the same reference identifier was used; it does not prove
who initiated the payment.

### Amount discrepancy (high)

Screenshot OCR: `4,500`. Ledger: `45,000`. Difference: `40,500`. The finding lists both source
locators and warns that OCR can misread digits.

### Payee mismatch (high)

The invoice and screenshot claim `gov-security@upi`; the ledger pays `fraud-mule@okaxis`.
A conflict edge is added. This is a discrepancy requiring review, not a fraud verdict.

### Shared identifiers (correlation)

- `phone +91-98765-43210` appears in the call log and chat.
- `upi_vpa gov-security@upi` appears in the invoice and screenshot OCR.
- `utr 312456789012` appears in the screenshot and ledger.
- `filename invoice_45000.pdf` appears in the chat attachment and invoice evidence.

These are exact normalized matches, labelled as correlation findings.

### Authentication indicator (high suspicion)

The auth log has 8 failures within 60 seconds and 10 failures within 15 minutes from
`203.0.113.45`, with multiple usernames and invalid users. The parser creates a threshold-based
finding. It is **not** linked to the financial events merely because the timestamps are near
each other.

### Timestamp uncertainty (low, data quality)

Syslog lines omit the year and timezone; call/chat/transaction rows are timezone-ambiguous.
Each affected evidence record gets a low-severity data-quality finding explaining the
assumption.

## Benign control

`sample_data/benign_control/` contains:

- Invoice `INV-2026-9913`: subtotal `45,000`, CGST 9% `4,050`, SGST 9% `4,050`, total
  `53,100`, payee `vendor-support@icici`.
- UPI statement: `53,100` to `vendor-support@icici`, UTR `412456789099`.

Expected outcome: an informational **Values reconcile** finding. No high/medium reconciliation
anomaly should be produced for the legitimate invoice.

## What to verify in the UI

- **Dashboard:** real evidence/event/finding counts.
- **Evidence vault:** SHA-256 values, integrity verification, source previews.
- **Auth analysis:** event table, rule reasons, source-line drawer, JSON/CSV export.
- **Timeline:** normalized and raw timestamps, confidence badges, undated section.
- **Graph:** exact matches and conflicts are visually distinct from heuristic temporal leads.
- **Findings:** severity, detection method, limitations, alternatives, evidence links, review.
- **Reports:** PDF/JSON with hashes, findings, audit and the draft-only Section 63 section.

## Important non-claims

- The synthetic screenshot is not a real payment confirmation.
- The synthetic auth log is not a real intrusion.
- The tool does not declare the victim, sender, or recipient guilty.
- The amount mismatch and payee mismatch are indicators requiring corroboration and human
  review.
- The report is a draft and is not automatically court-admissible.
