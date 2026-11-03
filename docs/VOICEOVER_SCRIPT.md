# Red Thread prototype — video analysis and voice-over script

## Recording guide

Play the shorter recording first, followed by the longer recording. The combined running time is approximately **3 minutes 7 seconds**. All timestamps below restart at the beginning of their respective video. The narration is written for the existing footage, including loading screens; no cuts are required.

Use a clear, measured product-demo voice, approximately 125–145 words per minute. Begin each passage at its cue and allow a brief pause if you finish before the next cue. Read only the narration column aloud. Say “PhishTrace” as “fish trace,” “SHA-256” as “S-H-A, two fifty-six,” and “UPI” as “U-P-I.”

The project folder is named `raksha`, but the application and report use **Red Thread**. The script follows the visible product name.

## Prototype analysis

Reviewed the project documentation, frontend workspaces, evidence-preservation service, and reconciliation implementation, then inspected extracted frames from the shorter recording before the longer recording. Both recordings are silent screen captures, 816 × 480, with no audio stream. This was a source-and-recording review; it does not establish that every feature was independently exercised in a fresh running instance.

The prototype's central workflow is evidence intake → preservation and hashing → parsing and event extraction → correlation and reconciliation → investigator review → report export. Its strongest demonstration is the connection between a visible discrepancy, its supporting source records, and a reviewable finding. The optional AI assistant extends this workflow with case-grounded answers and citations; the core processing is implemented independently of AI.

The shorter clip establishes the workspace: dashboard summaries, case selection, investigator-controlled status, audit history, and evidence inventory. The Operation PhishTrace overview shows seven evidence files, 141 events, and 47 open findings. Those are the recorded case's current counts, not performance or accuracy measurements.

The longer clip demonstrates authentication analysis, a relationship graph, severity filtering, a finding's supporting records and review controls, invoice and screenshot previews, the unified timeline, a cited AI response, and an exported PDF. The intake page is shown without an upload being completed. The report sequence opens an existing PDF; the script describes the export capability without claiming a new report was generated on camera. The review controls are shown without a saved acceptance decision.

The sample case is synthetic. Its payment screenshot claims ₹4,500, while the ledger records ₹45,000 under the same UTR; the project also detects differing claimed and recorded payees. These are discrepancies requiring corroboration. Hash verification compares stored bytes with their recorded intake digest. Neither a matching hash nor a shared identifier independently establishes authenticity, ownership, intent, or guilt. The script preserves these distinctions without interrupting the demonstration.

## Video 1 — workspace and case overview

**Source:** `/home/akshut/Sutram/document_6248933938278967269.mp4`  
**Duration:** 00:40.400

| Time | Screen cue | Narration |
|---|---|---|
| 00:00–00:07 | Dashboard and active-case selector | Meet Red Thread, a digital forensics prototype that brings fragmented evidence into one investigation workspace. |
| 00:07–00:14 | Dashboard charts, recent evidence, latest findings | The dashboard summarizes case activity, evidence files, event types, and findings that need an investigator's attention. |
| 00:14–00:22 | Cases list, then Operation PhishTrace overview | Opening Operation PhishTrace brings the synthetic case's evidence, events, and findings into one overview. |
| 00:22–00:28 | Case status saved; evidence and findings in the overview | Investigators can update case status and notes while keeping the investigation's context together. |
| 00:28–00:34 | Audit trail | The audit trail records uploads, verification checks, and case updates for later review. |
| 00:34–00:40.400 | Evidence inventory and integrity controls | The evidence vault lists each file, its recorded hash, processing status, and integrity result. |

## Video 2 — investigation and reporting

**Source:** `/home/akshut/Sutram/document_6248933938278967270.mp4`  
**Duration:** 02:26.183

| Time | Screen cue | Narration |
|---|---|---|
| 00:00–00:06 | Evidence detail drawer, then intake page | From the evidence vault, we can inspect original files and prepare new evidence for processing. |
| 00:06–00:14 | Authentication summary, alerts, and parsed event table | Authentication analysis highlights login activity and suspicious patterns, with parsed events available for closer review. |
| 00:14–00:24 | Relationship graph loading | Behind these views, Red Thread extracts structured events and identifiers from logs, chats, invoices, payment records, and images. |
| 00:24–00:35 | Relationship graph loading continues | It compares shared identifiers across sources, keeping exact matches separate from conflicts and tentative leads. The core checks work independently of AI. |
| 00:35–00:45 | Graph appears; node selected | The relationship graph brings evidence, events, and entities together. Selecting a node reveals its details and connections. |
| 00:45–00:54 | Findings register and high-severity filter | Findings can be filtered by severity, helping investigators focus on amount discrepancies, payee mismatches, and other issues. |
| 00:54–01:06 | Finding explanation, supporting records, review controls, then register | Opening a finding reveals its explanation, supporting records, limitations, and alternative explanations. Investigators can record a review decision after checking the evidence. |
| 01:06–01:22 | Vault, invoice preview, screenshot preview | Back in the vault, we inspect the invoice and payment screenshot directly. SHA-256 verification checks whether stored bytes match their intake hash; it does not establish whether a file was authentic before upload. |
| 01:22–01:34 | Timeline loads, then event sequence and confidence badges | The unified timeline places extracted events in sequence, while flagging inferred dates and uncertain timestamps. This helps investigators distinguish recorded facts from assumptions. |
| 01:34–01:44 | AI workspace; discrepancy question submitted | The optional AI assistant answers questions using selected case records. Here, we ask it to explain the payment discrepancy. |
| 01:44–01:54 | AI response pending | In this synthetic case, the screenshot shows four thousand five hundred rupees, while the ledger records forty-five thousand under the same transaction reference. |
| 01:54–02:02 | Answer, citations, uncertainties, and next steps | The response includes source citations, uncertainties, and suggested next steps, giving investigators references to verify. |
| 02:02–02:12 | Reports workspace; existing PDF opened | The reporting workspace provides PDF and JSON exports that capture evidence hashes, findings, timeline events, and review information. |
| 02:12–02:22 | PDF evidence inventory, timeline, and findings | The report keeps these details together for review. Findings remain investigative indicators, and the export is a draft requiring human assessment. |
| 02:22–02:26.183 | Return to dashboard | Red Thread: connecting evidence, with investigators in control. |

## Optional presentation improvements

- The graph spends approximately 20 seconds loading, and the AI request approximately 15 seconds pending. The script fills these intervals with relevant explanation. For a shorter promotional edit, trim those waits and shorten the corresponding narration together.
- The 816 × 480 capture makes small source text and graph labels difficult to read. A new capture at 1080p or higher, with closer views of the finding and its two payment sources, would make the discrepancy easier to follow.
- The displayed PDF is an earlier snapshot: its first page shows six evidence files and one verified file, while the later vault view shows seven files with verified badges. Generate a fresh report after verification for a future recording so the report and workspace reflect the same investigation state.
- For the existing footage, the script avoids equating all 47 findings with confirmed threats. The register includes data-quality and correlation findings as well as higher-severity discrepancies.

## Source references within the project

- `README.md`: product scope and investigation workflow.
- `docs/DEMO.md` and `sample_data/operation_phishtrace/README.md`: synthetic scenario and expected discrepancies.
- `docs/LIMITATIONS.md`: hash, timestamp, OCR, correlation, AI, and reporting boundaries.
- `backend/app/services/evidence_service.py`: original-file intake, digest recording, and integrity verification.
- `backend/app/services/reconciliation_service.py`: deterministic findings and cross-source comparisons.
- `frontend/src/pages/CaseOverviewPage.tsx`, `AuthAnalysisPage.tsx`, `FindingsPage.tsx`, and `ReportsPage.tsx`: visible workspace behavior and controls.
