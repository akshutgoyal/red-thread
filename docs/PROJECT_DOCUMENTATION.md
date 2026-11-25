# Red Thread - Detailed Project Documentation

**Digital Forensics Investigation Framework**

Version 1.0 | Last updated 2026-11-25

---

## Table of contents

1. [Problem statement](#1-problem-statement)
2. [Objectives](#2-objectives)
3. [Proposed solution](#3-proposed-solution)
4. [System architecture](#4-system-architecture)
5. [Methodology](#5-methodology)
6. [Implementation](#6-implementation)
7. [Technologies used](#7-technologies-used)
8. [Results](#8-results)
9. [Future scope](#9-future-scope)

---

## 1. Problem statement

### 1.1 The investigative reality

A modern financial or cyber investigation produces evidence in fragments. A single case may
contain a call detail record, a chat export, a bank statement, an invoice PDF, a payment
screenshot, a GPS track, CCTV metadata, a device log and an SSH authentication log. Each arrives
in a different format, from a different source, under a different clock, and none of them
individually tells the investigator what happened.

Today that work is done by hand: exporting each source separately, opening files in different
tools, and building a timeline in a spreadsheet. Three specific failures follow from this.

**Failure 1: Correlation is manual and unrecorded.** Establishing that a phone number in a call
record also appears in a chat export is straightforward, but doing it across nine sources and
hundreds of records is not. When the investigator does make a connection, the reasoning is
usually recorded in their head or in unstructured notes. Nothing records *which two rows* were
linked, *by what rule*, and *how strong* the link was. The result is unverifiable.

**Failure 2: Evidence provenance is lost.** Once a record is copied into a spreadsheet, it is no
longer tied to the file and line number it came from. Months later, in court or in a review
meeting, nobody can answer "where exactly does this assertion come from?" without redoing the
work. Integrity checking, where it happens at all, is manual.

**Failure 3: Automated tools overstate their conclusions.** Existing automation tends to collapse
the distinction between what the evidence *shows* and what the tool *infers*. A failed-login burst
is reported as "attack detected". Two records that share a phone number are reported as "same
person". A model's guess is presented alongside a hashed file with no visual distinction. This is
dangerous in a courtroom, where the difference between an observation and an inference is the
difference between admissible and not.

### 1.2 The legal dimension

Under the Bharatiya Sakshya Adhiniyam, 2023, electronic records are admissible under Section 63
only with a prescribed certificate (Part A by the party in control of the device, Part B by an
expert), stating the hash value and algorithm. Practitioners report that the certificate is
routinely prepared from memory or from an outdated Section 65B template, that hash values are
mistyped rather than copied from the tool's report, and that the hash report is not attached.

The failure here is not analytical, it is documentary: the technical work was done, but the
evidence needed to present it was not captured at the time it was available.

### 1.3 Problem statement

> There is no open, local-first tool that ingests heterogeneous digital evidence, preserves
> verifiable provenance for every derived record, correlates identifiers across sources with
> explainable rules, and produces output that clearly separates what the evidence shows from what
> the tool infers - while remaining usable by an investigator who is not a forensic specialist.

---

## 2. Objectives

### 2.1 Primary objectives

| # | Objective | Success criterion |
|---|---|---|
| O1 | Ingest heterogeneous evidence without modifying it | Original bytes retrievable; SHA-256 matches on re-verification |
| O2 | Normalize all sources into one event model | Every record yields an event with raw timestamp, normalized timestamp and source locator |
| O3 | Correlate identifiers across sources with explainable rules | Every relationship names its rule and cites its supporting records |
| O4 | Preserve provenance to the record level | Every derived record resolves to `file:locator` |
| O5 | Distinguish observation from inference mechanically | Every record carries a classification that the UI and report cannot blur |
| O6 | Produce a court-oriented draft report | Required sections present; no fabricated attestation |
| O7 | Remain usable by a non-specialist | The workflow is derivable from real case state, not memorized |

### 2.2 Secondary objectives

- O8: Keep AI optional and non-authoritative; the deterministic pipeline must be complete without it.
- O9: Protect personal data when an external model is used.
- O10: Run entirely locally with no cloud dependency for the core workflow.
- O11: Make the same code deployable to a managed environment without modification.

### 2.3 Explicit non-objectives

Stating these up front prevents scope drift and, more importantly, prevents the tool from making
claims it cannot support:

- Not a guilt/fraud determination system.
- Not an automated certificate authority for Section 63.
- Not a replacement for an examiner's judgement.
- Not a trained machine-learning classifier (see section 5.4 for why).

---

## 3. Proposed solution

### 3.1 Core idea

Red Thread is a **provenance-first investigation pipeline**. The design principle is that
analysis and accountability are produced by the same pass: you cannot generate a finding without
also generating the record of how you got there.

```
Ingest -> Hash & preserve -> Parse & normalize -> Extract entities
      -> Correlate (explainable) -> Reconcile (deterministic)
      -> Reconstruct -> Human review -> Report
```

Every arrow in that chain leaves a durable, queryable record. The chain is the product.

### 3.2 The four-part solution

**Part 1: Immutable evidence with verifiable integrity.**
Files are stored byte-for-byte under generated names, with the SHA-256 recorded at intake and
recomputable on demand. The original filename is metadata, never a path. Uploaded content is
never executed.

**Part 2: One canonical event model.**
Thirteen parsers converge on a single `Event` shape. Critically, it keeps three things together
that are usually separated: the raw timestamp as written, the normalized timestamp in UTC, and a
label stating which assumption was needed to get from one to the other (`exact`,
`inferred_year`, `assumed_timezone`, `unknown`). An event that cannot be dated is kept and shown
separately rather than dropped or forced into a position.

**Part 3: Explainable correlation with a fixed classification.**
Eight rule families produce relationships. Each carries its rule, its supporting evidence rows,
the exact source locators, a confidence and a classification from a closed set
(`observation`, `correlation`, `inference`, `hypothesis`). A separate, deliberately simple
scoring layer ranks leads without ever creating or reclassifying one.

**Part 4: Output that cannot overstate itself.**
The report and the UI share one vocabulary. Every AI answer is labelled. Every count comes from
one service. The Section 63 annexure contains the prescribed fields, all blank, because the tool
cannot attest to a device it never examined.

### 3.3 Why this shape

The alternative - a tool that produces a confident narrative - is easier to build and is what
most automation does. It was rejected because in a legal context a confident wrong answer is
worse than an honest partial one. Every design decision that follows, including the refusal to
let the ML layer create edges and the refusal to auto-fill the certificate, comes from that
choice.

---

## 4. System architecture

### 4.1 Layered view

```
PRESENTATION
  React 19 SPA - 16 routed pages
  Crime Reconstruction workspace (6 tabs)
  Guidance layer (stepper, page guides, 48-step tour engine)

        |  REST /api  (typed client, TanStack Query, credentials: include)

APPLICATION
  FastAPI routers -> services -> parsers
  Cross-cutting: auth gate, CSRF origin check, rate limiting,
                 request-scoped case isolation

        |  SQLAlchemy 2.0 ORM

DOMAIN
  Parser registry (13 parsers)
  Correlation engine (8 rule families) + lead scorer
  Reconciliation engine (4 check families)
  Count service (single source of truth)
  Guidance / narrative / reconstruction services

        |  Storage abstraction (local | R2)

DATA
  SQLite (local) | PostgreSQL (deployed)  - 16 tables
  Evidence objects - local filesystem | Cloudflare R2
```

### 4.2 Data flow

```
Upload
  -> validate (size, extension, emptiness, path safety)
  -> SHA-256 (streamed)
  -> store under generated key
  -> Evidence row (processing_status = uploaded)

Parse
  -> delete prior derived rows for this evidence (idempotent re-parse)
  -> parser registry selects a parser
  -> ParseResult { events, warnings, accepted, rejected }
  -> Event rows + Entity rows + EventEntity links
  -> warning classification (what / why / fix / still usable)
  -> Evidence row updated (parser, version, status)

Analyze
  -> correlation engine: 8 rule families -> Relationship + RelationshipSupport
  -> lead scorer: fixed-weight ranking -> metadata_json.ml_assist
  -> reconciliation: 4 check families -> Finding + FindingEvidence
  -> count service: canonical numbers for every surface

Review
  -> ReviewDecision (immutable history) + current review_status
  -> InvestigatorAnnotation (any target type)
  -> AuditEvent on every mutation

Output
  -> Report (PDF via ReportLab, JSON) from one snapshot
  -> Section 63 annexure with prescribed fields, all blank
```

### 4.3 Data model

Sixteen tables. Every child cascades on case deletion.

| Group | Tables |
|---|---|
| Core | `cases`, `evidence`, `events`, `entities`, `event_entities` |
| Analysis | `findings`, `finding_evidence`, `relationships`, `relationship_supports` |
| Human input | `review_decisions`, `investigator_annotations` |
| Output and audit | `reports`, `ai_queries`, `audit_events`, `graph_edges`, `users` |

Three constraints carry most of the integrity guarantee:

1. `entities` is unique on `(case_id, entity_type, value_normalized)`, so the same identifier
   cannot be duplicated by normalization variance.
2. `relationships` is unique on the full edge identity including `correlation_rule`, so a rebuild
   is idempotent rather than cumulative.
3. `relationship_supports` makes provenance structural: a relationship with no support row cannot
   exist through the normal path.

### 4.4 Deployment architecture

```
Vercel (React SPA, static, CDN)
   |
   | HTTPS
   v
Render (FastAPI in Docker, non-root, Tesseract)
   |                    |
   v                    v
Supabase Postgres    Cloudflare R2 (private)
(metadata)           (evidence + reports, streamed)
   |
   v
Isoquant / CommandCode / TokenHarbor (optional AI)
```

The API is stateless: Render's disk is ephemeral, Supabase and R2 persist. Evidence and reports
are private R2 objects streamed through the API; no anonymous object URL is ever issued. The same
service code runs locally against SQLite and the filesystem, so local and deployed differ only in
configuration.

### 4.5 Security architecture

| Layer | Control |
|---|---|
| Transport | HSTS, `X-Frame-Options: DENY`, `nosniff`, referrer policy, restrictive CSP |
| Session | Signed JWT in HttpOnly cookie, `SameSite=None; Secure`, 7-day TTL |
| CSRF | Origin allowlist enforced on all mutating `/api` requests |
| Authorization | Per-request case ownership check; 404 for missing, 403 for foreign |
| Rate limiting | Five route classes, keyed by hashed client identity |
| Proxy trust | `X-Forwarded-For` honoured only for configured hops |
| Upload | Size/extension/emptiness validation, path traversal rejection, never executed |
| Data | CSV formula-injection sanitizer, private object storage |
| Secrets | Backend-only; never returned by the API, never in reports or logs |

---

## 5. Methodology

### 5.1 Development approach

The project was built **additively on an existing working system**, not rewritten. Each change
had to satisfy the same constraint: do not duplicate an existing capability, do not break the
deterministic pipeline, and do not introduce a claim the evidence cannot support.

Work proceeded in vertical slices: a capability was taken end to end (parser -> event -> entity
-> relationship -> UI -> report) before the next was started. This kept the system runnable at
every commit and made regressions immediately visible.

### 5.2 Evidence handling methodology

**Preservation.** Files are hashed on ingest while streaming, so a large file is never fully
buffered. The hash is the identity anchor: re-verification recomputes it from storage rather than
from anything cached.

**Parse isolation.** Re-parsing deletes derived rows for that evidence first. Without this, a
second parse would double every event and silently inflate every downstream count. The failure
mode is dangerous because it produces plausible larger numbers, not an error.

**Degradation over failure.** A parser that cannot fully interpret a file emits warnings rather
than failing the upload. Every warning is classified into four answers: what happened, why, how
to fix it, and whether the data is still usable. A partially parsed file is therefore actionable
rather than merely broken.

**Explicit mapping.** When columns cannot be confidently matched, the file is held for explicit
column mapping instead of guessed at. A wrong guess silently produces wrong events, which is the
worst possible failure for this class of tool.

### 5.3 Correlation methodology

Rules were designed so that each answers a distinct investigative question and produces a
falsifiable claim:

| Rule | Question answered | Why it is not "the same person" |
|---|---|---|
| `shared_identifier` | Does this exact value appear in two independent files? | A number can be shared, spoofed or reassigned |
| `co_mention` | Are two entities named in the same record? | Co-occurrence in a document is not a relationship |
| `temporal_association` | Do records sharing an identifier occur close in time? | Proximity is not causation; clocks drift |
| `spatial_proximity` | Are documented coordinates near in space and time? | Proximity does not establish presence over an interval |
| `communication_sequence` | Do several communications share an identifier? | Sequence is not coordination |
| `device_auth_context` | Do auth and device records share an identifier? | Shared account context is not a proven operator |
| `geo_velocity_anomaly` | Does implied travel speed exceed a threshold? | Timestamps or coordinates may be wrong - that is the point of flagging it |
| `cctv_coverage_gap` | Is there a recording gap for one camera? | A gap is not proof of missing activity |

Three guardrails were applied consistently:

1. **Cross-source requirement.** `shared_identifier` fires only when the value appears in two
   *different* evidence files. The same value twice in one file is one source, not corroboration.
2. **Classification ceiling.** Speculative rules are capped at `hypothesis` by construction, not
   by convention.
3. **Idempotent rebuild.** A re-run removes stale auto-generated rows but never removes a
   relationship that a human reviewed or annotated. Human work is never destroyed by
   recomputation.

### 5.4 Why the ML layer is deliberately small

A trained classifier was considered and rejected for this version. Three reasons:

1. **Explainability.** A weight vector with eight named features can be shown to an investigator
   and defended in review. A learned model's reasoning cannot.
2. **No training data.** There is no labelled corpus of confirmed relationships, and inventing one
   from synthetic data would produce a model that learns the synthetic data.
3. **Separation of powers.** The risk with ML here is not weak predictions, it is silent
   reclassification. The layer is therefore constrained by design: fixed hand-set weights, no
   training step, no ability to create a relationship, no ability to change a type.

The result is a scorer that orders leads and can be audited line by line. Its limitation is
stated rather than hidden: it reorders, it does not discover.

### 5.5 Verification methodology

Four levels, each catching a different class of defect:

| Level | Method | Catches |
|---|---|---|
| Unit / integration | 190 backend tests | Logic errors, contract breaks |
| Component | 54 frontend tests | Render errors, state bugs |
| Static | Anchor existence and route reachability tests | Steps that point at nothing |
| Live | Browser walkthrough against the deployed build | Everything the above cannot |

The static layer exists because of a specific class of bug: a guided-tour step whose anchor
string appears in the source but never renders on the route the step navigates to. Unit tests
passed, the type checker passed, and the feature was still broken for the user. The lesson
recorded in the codebase is that "the identifier exists somewhere" is not the same as "the user
can reach it", and only a route-aware assertion tests the second.

---

## 6. Implementation

### 6.1 Backend

**Scale:** 17,875 lines of application code, 5,029 lines of tests.

| Module | Responsibility |
|---|---|
| `main.py` | App factory, middleware chain, security headers, lifespan seed |
| `config.py` | 54 settings, all `RED_THREAD_` prefixed |
| `database.py` | Engine, sessions, lightweight in-place migrations |
| `rate_limit.py` | Per-route-class token buckets |
| `api/` | 9 routers, 48 endpoints |
| `parsers/` | 13 registered parsers |
| `services/` | 25 services (analysis, output, infrastructure) |
| `models/` | 16 SQLAlchemy models |

**The parser registry.** Thirteen parsers in a fixed detection order, selected by content and by
filename/extension hints. Each returns a `ParseResult` with accepted and rejected counts, so a
partially parsed file reports its own loss rather than appearing complete.

**The count service.** A single module computes every number the application displays. This was
introduced after observing a real defect: the graph page showed `60 total / 200 documented / -140
inferred`, because one surface mixed a capped rendered list with a full stored list. A negative
count is obviously wrong; the more common version of the same bug is two plausible numbers that
disagree, which the earlier design would have shown indefinitely.

The distinction between *relationships* and *connections* is deliberate and is measured, not
assumed. In the Digital Trail case the 202 stored relationships cover 146 unique entity pairs,
because 49 pairs carry more than one relationship under different rules. Unique connections
therefore reads 146 while total relationships reads 202, and both are correct: they answer
different questions. The codebase rule is that every surface states which of the two it is showing
and never mixes them.

**The guidance service.** Eleven stages whose completion conditions all read stored rows.
Opening a page does not complete a stage; producing the record does. This was a deliberate
correction: progress that advances by navigation teaches the wrong behaviour.

### 6.2 Frontend

**Scale:** 16,374 lines across 16 routed pages, 31 components, 37 query hooks.

The central UI decision was to consolidate the reconstruction surfaces. Previously three separate
sections (workspace, timeline, spatial) presented overlapping fragments of the same story. They
were merged into one workspace with six tabs ordered as an investigation actually proceeds:
Overview, Event reconstruction, Timeline, Relationships, Locations, Findings. Old routes are
preserved as redirects that forward deep links, so no bookmark breaks.

**Guidance layer.** Three cooperating pieces: a stepper driven by server-computed stage status, a
page guide answering "what is this / when to use it / what next" using live case state, and a tour
engine of 48 steps across 5 tours.

**Tour engine.** Steps target real DOM elements and wait for them to exist, using a
`MutationObserver` plus layout ticks rather than fixed delays, because the target often appears
only after a route render and a data load. The card stays mounted between steps so a click is
never lost to a scrim. A bounded fallback ensures no step can trap the user if its anchor never
appears.

### 6.3 The privacy layer

A boundary sits between Red Thread and any external model. Before a request leaves the process,
identifiers are replaced with stable tokens (`PERSON_01`, `PHONE_01`, `ACCOUNT_01`, `RECORD_01`).
Three sources feed it, in priority order: the case entity table (authoritative, catches short
bare values such as a username), key-based rules (a bare value under a `phone` or `account` key is
personal data by definition), and content patterns.

The mapping exists only in process memory for the duration of one request. It is never persisted,
logged, or transmitted. Responses are mapped back server-side, so the investigator reads real
values while the provider only ever saw tokens. A token the request never issued is left
untouched rather than resolved, so a model cannot fabricate an identity it was not given.

### 6.4 The report

One data snapshot feeds both PDF and JSON. The PDF carries 21 titled sections plus the title and
cover block, including the evidence register, provenance, chain-of-custody derived from
`audit_events`, an integrity table, a classification legend, a timeline, findings, spatial
observations, AI output explicitly separated, and the Section 63 annexure.

The annexure format was verified against published descriptions of the Schedule to the Bharatiya
Sakshya Adhiniyam, 2023 before implementation, not reconstructed from memory. It reproduces the
fields - source tick-box, device identifiers, lawful-control and device-working declarations,
hash value and algorithm, hash report, date/time/place, and separate Part A and Part B signature
blocks - and leaves every one of them empty.

### 6.5 Defects found and corrected during implementation

Recording these is part of the methodology, because each one changed the design:

| Defect | Root cause | Correction |
|---|---|---|
| Blank page, no console error | React hook-count mismatch: a `useMemo` placed after an early return | Memos moved above all returns |
| `-140 inferred relationships` | Mixed a capped rendered list with the full stored list | One count source |
| "Documented" showed 0 | Queried a classification that is derived, not stored | Derived as `observation` + `correlation` |
| Privacy badge never appeared | Pydantic response model silently dropped undeclared fields | Schema declared; a no-error class of bug |
| Report download returned 401 | Cross-site `<a href>` navigation does not reliably carry the cookie | Authenticated fetch + blob |
| Tour steps highlighted nothing | Steps routed through redirect-only legacy paths | Route-aware static test added |
| Filter anchor measured 0x0 | `display: contents` produces no layout box | Replaced with a measurable container |

The common thread is that none of these produced an exception. They produced plausible-looking
wrong output, which is precisely why the verification approach includes browser walkthroughs and
route-aware assertions.

---

## 7. Technologies used

### 7.1 Backend

| Technology | Version | Role | Justification |
|---|---|---|---|
| Python | 3.11+ (3.12 in Docker) | Runtime | Available on forensic workstations; strong parsing ecosystem |
| FastAPI | 0.148 | HTTP API | Typed request/response models that also act as validation |
| Pydantic | 2.14 | Schemas | Response models prevent accidental field leakage |
| SQLAlchemy | 2.1 | ORM | Same code on SQLite and Postgres |
| SQLite / PostgreSQL | - | Storage | Zero-config local; managed Postgres when deployed |
| ReportLab | 4.5 | PDF | Precise layout control needed for a formal document |
| pandas | 2.3 | Tabular parsing | Robust CSV handling |
| NetworkX | 3.7 | Graph assembly | Graph traversal without a graph database |
| pdfplumber / pypdf | 0.11 / 5.9 | PDF text | Invoice extraction, with a fallback |
| httpx | 0.28 | HTTP client | Async, and a mockable transport for tests |
| boto3 | 1.43 | R2 storage | S3-compatible API |
| PyJWT | 2.15 | Sessions | Signed stateless tokens |
| google-auth | 2.62 | Sign-in | ID token verification |
| pytest / respx | 8.4 / 0.23 | Testing | Async tests with mocked provider calls |
| Tesseract (optional) | - | OCR | Only external binary needed |

### 7.2 Frontend

| Technology | Version | Role |
|---|---|---|
| React | 19.1 | UI |
| TypeScript | 5.8 | Type safety |
| Vite | 7.3 | Build and dev server |
| Tailwind CSS | 3.4 | Styling via design tokens |
| TanStack Query | 5.80 | Server-state caching |
| React Router | 7.6 | Routing, tab deep links |
| Cytoscape.js | 3.32 | Relationship graph |
| Leaflet / React-Leaflet | 1.9 / 5.0 | Spatial view |
| Recharts | 2.15 | Charts |
| Vitest / Testing Library | 5.1 / 16.3 | Component tests |

### 7.3 Infrastructure

| Technology | Role |
|---|---|
| Docker | Reproducible backend image, non-root |
| Render | Backend hosting, health-checked |
| Vercel | Frontend hosting and CDN |
| Supabase | Managed PostgreSQL |
| Cloudflare R2 | Private object storage |

### 7.4 What was deliberately not used

| Rejected | Why |
|---|---|
| A graph database | NetworkX plus indexed SQL is sufficient at this scale; adds an operational dependency |
| A trained ML model | See section 5.4 |
| An ORM-level cascade for deletion | Explicit ordered deletes behave identically on SQLite and Postgres |
| Client-side PDF generation | The report must be generated from server-side data, not from what the browser holds |
| WebSockets | Analysis is request-scoped; polling-free simplicity was worth more than live updates |

---

## 8. Results

### 8.1 Functional results

All primary objectives were met.

| Objective | Result | Evidence |
|---|---|---|
| O1 Immutable ingest | Met | SHA-256 recomputed from storage matched on live check |
| O2 One event model | Met | 13 parsers emit the same shape; undated events retained separately |
| O3 Explainable correlation | Met | 8 rule families; every relationship carries rule + supports |
| O4 Provenance | Met | Every derived record resolves to `file:locator` |
| O5 Observation vs inference | Met | Closed classification set enforced in schema, UI and report |
| O6 Court-oriented report | Met | 22 sections; annexure fields blank; no fabricated attestation |
| O7 Non-specialist usable | Met | 11-stage journey derived from real state; 48 tour steps |
| O8 AI optional | Met | Full pipeline works with no provider configured |
| O9 Privacy | Met | 111 identifiers pseudonymised on a live request; mapping never transmitted |
| O10 Local-first | Met | SQLite + filesystem; no cloud dependency |
| O11 Deployable | Met | Same code on Vercel + Render + Supabase + R2 |

### 8.2 Measured evidence

**Synthetic cases (Operation Digital Trail).** 7 evidence files, 20 events, 38 entities,
7 findings, 202 relationships across six distinct types, 5 documented spatial observations.

Relationship distribution demonstrates the multi-type objective (O3) rather than a single generic
edge:

| Type | Count |
|---|---|
| `co_mention` | 83 |
| `shared_identifier` | 57 |
| `temporal_association` | 53 |
| `communication_sequence` | 4 |
| `spatial_proximity` | 3 |
| `device_auth_context` | 2 |

By classification the same 202 relationships split into 198 documented (observation or
correlation) and 4 inferred leads (hypothesis). The classification total reconciles exactly with
the relationship total, which is the property the count service exists to guarantee.

**Benign control.** A synthetic case containing a consistent invoice (`INV-2026-9913`) and its
matching UPI statement is the false-positive check. Measured result: the invoice *reconciles*
(`Values reconcile for invoice INV-2026-9913`, info), and there is **no high or medium
reconciliation anomaly**. The two remaining findings are a low-severity timestamp-uncertainty note
per file and a medium-severity `correlation` for the VPA shared between the invoice and the payment
that settles it - which is the expected, benign state rather than a discrepancy.

The distinction is the point. If a change to the reconciliation rules makes the control emit a
reconciliation anomaly, that change is wrong. Correlation findings are expected even in a clean
case, because a supplier's identifier legitimately appearing on its own invoice is not suspicious.

**Reconciliation.** The PhishTrace case yields, measured: three high-severity reconciliation
findings (amount discrepancy between screenshot OCR and ledger, payee mismatch between screenshot
and ledger, payee mismatch between invoice and transaction recipient), one informational exact-UTR
match, one high-severity authentication indicator for the failed-login burst, six medium
identifier-correlation findings and six low timestamp-uncertainty notes.

The high-severity authentication indicator is deliberately kept in a separate category from the
financial reconciliation findings, so a reader cannot mistake a login anomaly for proof about the
payment chain.

### 8.3 Quality results

| Metric | Result |
|---|---|
| Backend tests | 190 passed in 77.9 s |
| Frontend tests | 54 passed across 14 files in 43.5 s |
| Type check | Clean (`tsc -b`) |
| Lint | Clean (0 errors, 0 warnings) |
| Production build | Clean, 1.7 MB total, split into React / query / Cytoscape / charts / Leaflet chunks |
| Live API health | HTTP 200 in 0.68 s |

### 8.4 Performance observations

| Operation | Observed |
|---|---|
| API health check (deployed) | 0.68 s |
| Full correlation rebuild, 20-event case | 1.76 s, yielding 202 relationships over 146 unique pairs and 360 support rows |
| PDF generation, full case | 21-page document, 57 KB, for the 7-file Digital Trail case |
| AI answer (external provider) | 23 - 25 s including provider latency |

The AI latency is provider-bound, not application-bound. The deterministic pipeline completes
without it, which is why AI is optional rather than load-bearing.

### 8.5 Live verification

| Check | Result |
|---|---|
| Evidence streaming from private R2 | Content streamed through API; recomputed SHA-256 matched |
| Report download | 401 before fix, 200 with a valid PDF after; verified in production |
| AI grounding | 10 - 20 citations, all validated against stored records |
| Privacy layer | 111 identifiers tokenised; `mapping_included: false` |
| Case deletion | Case, 9 evidence files, 32 events, 4 findings, 83 relationships removed; all returned 404 after |

### 8.6 What the results show, and what they do not

The system demonstrably ingests, correlates and reports heterogeneous evidence with preserved
provenance, and it demonstrably refuses to overstate. It has been verified against synthetic
cases designed to exercise each capability, including a control case for false positives.

It has **not** been validated against a real criminal case, has not been assessed by a court, and
has not been through an independent forensic audit. The synthetic evidence is generated, clearly
labelled, and must never be presented as real. No claim of legal admissibility is made or implied.

---

## 9. Future scope

### 9.1 Near term - closes a known gap

**1. Generate the hash report as a separate artefact.** The Schedule to the BSA asks for the hash
report to be enclosed. The annexure currently provides the fields and the digests; producing a
dedicated, printable hash report per record is the most concrete remaining gap in the Section 63
preparation flow.

**2. Certificate of completeness for the report.** A mechanism that records which records were
included and excluded from a report, so an investigator can state affirmatively what the document
covers. This addresses the authenticity question that currently relies on the tool's own
assertion.

**3. Multi-user roles.** The current model is per-user case ownership. Investigative teams need
at least three roles (investigator, reviewer, read-only supervisor) with the audit trail
attributing actions to a real identity.

### 9.2 Medium term - deepens the analysis

**4. Cross-case correlation with explicit consent.** The same identifier often appears in two
unrelated cases. Correlating them is analytically valuable and legally sensitive. This requires a
deliberate, audited, per-case opt-in rather than a default.

**5. Learned confidence ranking, with the current model as a fallback.** If a labelled corpus of
reviewed relationships ever exists, a model could replace the fixed weights. The architectural
constraint should survive: it must rank, not create, and the fixed-weight scorer must remain
available as the explainable baseline.

**6. Additional parsers.** Banking statement PDFs (multi-page, table-based), WhatsApp and Signal
export formats, tower-dump files, and Windows event logs are the highest-value additions.

**7. Timeline gap analysis.** Detecting and explaining missing periods - a device that goes silent,
a camera with no footage - as first-class findings rather than as coverage-gap relationships.

### 9.3 Longer term - broader applicability

**8. Advanced privacy: on-premise models and homomorphic comparison.** Local pseudonymisation
reduces exposure but is pattern-driven. Running an on-premise model removes the exposure entirely;
secure comparison could allow cross-case matching without either side revealing identifiers.

**9. Formal court validation.** Working with a legal stakeholder to have the output format
reviewed by a court or a Section 79A examiner, and recording their feedback as a requirement set.
Without this, "court-oriented" is a design intent, not a validated property.

**10. Performance at scale.** The current design loads case data into memory for analysis. Cases
in the hundreds of thousands of events need streaming aggregation and precomputed indexes. The
existing work of moving filters server-side is the first step in that direction.

### 9.4 Deliberately out of scope

These are refused, not deferred, because implementing them would undermine the objectives:

- Automated guilt or fraud scoring.
- An automated Section 63 certificate generator that fills declarations.
- Silent fallback between AI providers.
- Fuzzy or name-only entity merging.
- Route or location inference not present in the evidence.

---

## Appendix A - Project statistics

| Metric | Value |
|---|---|
| Backend application code | 17,875 lines |
| Backend tests | 5,029 lines |
| Frontend code | 16,374 lines |
| Parsers | 13 |
| Relationship rule families | 8 |
| Reconciliation check families | 4 |
| Database tables | 16 |
| API endpoints | 48 |
| Frontend pages | 16 |
| Reconstruction tabs | 6 |
| Guidance stages | 11 |
| Tour steps / tours | 48 / 5 |
| Backend / frontend tests | 190 / 54 |

## Appendix B - Glossary

| Term | Meaning |
|---|---|
| Provenance | The recorded chain from a derived record back to the exact file and locator |
| Canonical event | The normalized record every parser produces |
| Entity | A distinct identifier extracted and deduplicated per case |
| Relationship | A persisted, explainable connection between two records |
| Documented | Derived count of relationships classified observation or correlation |
| Inferred lead | A relationship classified inference or hypothesis |
| Support row | The evidence/event/locator that produced a relationship |
| Match score | A ranking signal in 0-1, never a probability of guilt |
| Section 63 | The BSA 2023 provision governing electronic-record admissibility |
| Chain of custody | The recorded handling history of evidence |

## Appendix C - References

- Bharatiya Sakshya Adhiniyam, 2023, Section 63 and the Schedule (certificate format)
- Project README - setup, usage and configuration
- REQUIREMENTS.md - dependencies and software prerequisites
- docs/AI_INTEGRATION.md - AI architecture, citation validation, privacy layer
- docs/LIMITATIONS.md - the complete limitation list
- docs/AUTH_PARSER.md - authentication parser behaviour and thresholds
- docs/ARCHITECTURE.md - module-level architecture detail

---

**Red Thread does not replace an investigator. It preserves provenance, exposes its reasoning, and
keeps conclusions subject to human review.**
