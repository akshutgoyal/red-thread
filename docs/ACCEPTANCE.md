# PS3 live acceptance record

Date: 2026-11-04  
Frontend: <https://red-thread-virid.vercel.app>  
API: <https://red-thread-api.onrender.com/api>

## Deployment

- Published the PS3 upgrade to the existing `akshutgoyal/red-thread` repository.
- Render runs the additive schema and original two migrated cases alongside the new demo.
- Vercel serves the new workspace, review/annotation UI and Leaflet spatial view.
- The first Render rollout completed the Digital Trail seed but did not switch the public
  HTTP surface within the initial health window. A follow-up rollout after seed completion
  switched traffic successfully; the seed skipped the already-complete cases.

## Cases

| Case | Evidence | Events | Result |
|---|---:|---:|---|
| Operation Digital Trail (Synthetic Demo) | 7 | 20 | 202 relationships, 5 spatial observations, 3 spatial relationships |
| Operation PhishTrace (Synthetic Demo) | 7 | 141 | Existing case still loads (includes the earlier live test upload) |
| Benign Control (Synthetic Demo) | 2 | 3 | Existing control still loads |

The Digital Trail relationship mix was 83 co-mentions, 53 temporal associations, 57 shared
identifiers, 4 communication sequences, 2 device/auth contexts and 3 spatial proximities.

## Live checks

- **CORS:** preflight from `https://red-thread-virid.vercel.app` returns 200 with the exact
  allowed origin.
- **R2:** evidence content streamed through the API; recomputed SHA-256 matched the stored
  evidence digest.
- **Review/annotation:** an accepted review and a case annotation persisted; the audit trail
  contained 719 events at check time.
- **Reports:** JSON included `relationships`, `annotations`, `review_decisions`, `unresolved`,
  `audit` and `spatial_observations`; all 202 relationships carried support rows. The PDF was
  generated and downloaded successfully (48,122 bytes).
- **AI:** focused on `DEV-DT-01`, TokenHarbor returned a grounded answer in 25.0 s with 10
  citations and `insufficient_evidence=false`. It separated documented GPS/device evidence
  from spatial and chat leads.
- **Spatial UI:** browser verification showed the Leaflet/OpenStreetMap view, five documented
  observations and the three spatial-proximity relationships.
- **Workspace UI:** browser verification showed the review queue and relationship explanations
  in the live workspace.

## Local verification

- Backend: `97 passed` with `pytest -q`.
- Frontend: `npm run lint` and `npm run build` pass.
- Digital Trail end-to-end test covers multi-source ingestion, provenance, spatial data,
  relationship review, annotation, report JSON and support rows.
- Synthetic generator produces the seven Digital Trail files and updates
  `sample_data/manifest.json`.

## Caveats

- The deployed demo is public and has no authentication.
- Reports are draft-only and not automatically court-admissible.
- Spatial and temporal links are investigative leads, not proof.
- AI output remains an interpretation requiring human verification.
- `npm audit` reports 16 dependency findings; they require a separately reviewed upgrade.
