# Benign Control — SYNTHETIC DEMO DATA

This directory is a **synthetic benign control** for Red Thread. It is not real evidence.

## Files

- `invoice_legit.pdf` — invoice `INV-2026-9913`:
  - Subtotal: `INR 45,000.00`
  - CGST (9%): `INR 4,050.00`
  - SGST (9%): `INR 4,050.00`
  - Total: `INR 53,100.00`
  - Payee VPA: `vendor-support@icici`
- `upi_statement.csv` — a matching transaction:
  - UTR `412456789099`
  - Amount `53,100.00`
  - Payee `vendor-support@icici`
  - Status `SUCCESS`

## Expected outcome

The invoice total, GST arithmetic and transaction amount reconcile. Red Thread may create an
informational reconciliation finding, but it must not produce a high-severity amount or payee
discrepancy for this control. This demonstrates restraint: a normal record does not become
suspicious merely because the tool can analyze it.
