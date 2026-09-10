# SSB26188 screening contracts

The canonical agreement between every component of the screening system: the
Python inference services, the fusion engine, and the officer-facing React
Native application.

Before this existed the four components disagreed with each other in ways that
would have produced confident, wrong answers in the field. The most serious was
face verification: the app assumed a match boundary of `0.85` on what it treated
as a 0–1 confidence, while the ArcFace pipeline emits a **raw cosine
similarity** where `0.30` is a normal match. Feeding real scores into the old
assumption would have read almost every genuine subject as an impostor.

---

## Where things live

| Artefact          | Path                                                        | Role                               |
| ----------------- | ----------------------------------------------------------- | ---------------------------------- |
| **Wire schema**   | `contracts/schemas/ssb-screening.schema.json`               | Source of truth                    |
| Python mirror     | `contracts/python/ssb_contracts/`                           | Dependency-free package            |
| TypeScript mirror | `src/contracts/index.ts`                                    | Consumed by the app                |
| **Thresholds**    | `contracts/config/thresholds.json`                          | Every band, weight and boundary    |
| Mock DINOv2       | `contracts/python/ssb_contracts/services/forensics_mock.py` | Tamper detection stand-in          |
| Fusion engine     | `contracts/python/ssb_contracts/services/risk_fusion.py`    | Evidence fusion                    |
| Adapters          | `contracts/python/ssb_contracts/adapters/`                  | Existing services → contract       |
| Fixture generator | `contracts/python/tools/generate_screening_fixtures.py`     | Produces `src/fixtures/screening/` |

Parity is enforced, not hoped for: `contracts/python/tests/test_contracts.py`
and `__tests__/contracts.test.ts` both read the JSON schema and fail if their
language mirror has drifted from it.

---

## Integration status

| Module                | State           | Backed by                  | Notes                                                        |
| --------------------- | --------------- | -------------------------- | ------------------------------------------------------------ |
| **OCR / MRZ**         | `MOCK`          | services/extraction (PP-OCRv5 + U-Net) | Service is built and adapted; not yet reachable from the app |
| **Validation**        | `MOCK`          | `services/validation`       | Deterministic rules built and adapted; not yet wired         |
| **Face verification** | `MOCK`          | ArcFace R50 (`buffalo_m`)  | Pipeline built and adapted; thresholds provisional           |
| **DINOv2 forensics**  | `MOCK`          | `mock-dinov2-v0`           | **Not implemented.** No model, no weights, no data           |
| **PatchCore anomaly** | `NOT_AVAILABLE` | —                          | **Not built.** Never fabricated, never scored                |
| **Risk fusion**       | `ACTIVE`        | Evidence Fusion Engine     | Deterministic weighted fusion — _not_ LightGBM               |
| **Officer app**       | `ACTIVE`        | Expo SDK 54 / RN 0.81      | Consumes the case document; holds no inference logic         |

`MOCK` here means the Python service exists and satisfies the contract, but the
app is not yet calling it over HTTP — it replays generated results instead. The
same table is rendered in the app under **Settings → Integration status** and
**Device setup**, so nobody evaluating a finding has to guess what produced it.

---

## The envelope

Every module response, whatever produced it:

```json
{
  "schema_version": "1.0",
  "case_id": "SSB-2026-0042",
  "module": "document_forensics",
  "status": "SUCCESS",
  "model_version": "mock-dinov2-v0",
  "timestamp": "2026-09-09T06:01:18.973Z",
  "result": {},
  "errors": []
}
```

`status` has four values, and the distinction between the last two is the one
the whole design rests on:

| Status          | Meaning                                                                            |
| --------------- | ---------------------------------------------------------------------------------- |
| `SUCCESS`       | Ran, produced a complete result                                                    |
| `PARTIAL`       | Ran, produced a usable but incomplete result                                       |
| `FAILED`        | Ran and could not finish                                                           |
| `NOT_AVAILABLE` | Did not run — not implemented, not deployed, or unsupported for this document type |

**`FAILED` and `NOT_AVAILABLE` are absences of evidence, never findings.** They
are excluded from scoring, drawn in neutral tones, and described to the officer
as checks that did not happen.

One invariant is enforced in code on both sides: `result` is `null` whenever
`status` is `FAILED` or `NOT_AVAILABLE`. A consumer that sees a non-success
status can stop reading, because there is provably nothing behind it. The Python
`Envelope` raises on construction if this is violated; TypeScript exposes
`hasEvidence()` as a type guard.

---

## Face verification

```json
{
  "similarity": 0.31,
  "decision": "MATCH",
  "thresholds": { "match": 0.3, "review": 0.14 },
  "quality": {
    "document_face": { "acceptable": true, "score": null, "metrics": {} },
    "live_face": { "acceptable": true, "score": null, "metrics": {} }
  }
}
```

`similarity` is a **raw cosine similarity in [-1, 1]** between two 512-D ArcFace
embeddings. It is not a probability and not a percentage. It is displayed as
`0.31`, never `31%`, and never rescaled.

The thresholds travel _with_ the result so a later re-tuning cannot change the
meaning of a stored case.

### One deliberate deviation from the brief

The brief specified `quality: { document_face: 0.91, live_face: 0.95 }`. The
ArcFace pipeline provides no such number — `QualityResult` is pass/fail gates
plus raw measurements (blur, brightness, a yaw proxy). Emitting `0.91` would
have been exactly the fabricated confidence the same brief forbids.

So `score` is **nullable** and stays `null` until a model actually produces one;
`acceptable` carries the gate and `metrics` carries the measurements in their
own units. The UI renders "Acceptable" plus the measurements. The field is kept
in the contract so a future quality model needs no schema change.

---

## Validation

```json
{
  "decision": "REVIEW",
  "checks": [{ "rule_id": "mrz_checksum", "status": "FAIL", "message": "…" }],
  "summary": { "passed": 6, "failed": 1, "review": 0, "not_applicable": 1, "not_available": 0 },
  "rule_version": "backend-validation-1.0.0"
}
```

Validation is deterministic evidence. **A rule failure does not mean the document
is fake** — a misread character produces the same failure as an alteration — and
the UI says so in as many words.

### A second deliberate deviation

The brief specified three check statuses (`PASS | FAIL | NOT_AVAILABLE`). The
contract carries five, because the existing engine already distinguishes cases
that collapsing would destroy:

- `REVIEW` — the rule ran and was inconclusive. Collapsing it into `FAIL` would
  turn an inconclusive check into an `INVALID` document.
- `NOT_APPLICABLE` — the rule is irrelevant to this document type (an expiry rule
  on a document with no expiry).
- `NOT_AVAILABLE` — the rule could not run because its input was missing.

The last two are both "not a failure", but they answer different questions, and
an officer defending a decision needs to know which one applied.

---

## Document forensics — MOCK

```json
{
  "tampered": true,
  "tamper_score": 0.91,
  "manipulation_type": "PHOTO_REPLACEMENT",
  "type_score": 0.87,
  "suspicious_regions": [{ "bbox": [0.08, 0.28, 0.27, 0.45], "score": 0.94 }]
}
```

`bbox` is `[x, y, width, height]` **normalised 0–1** against the corrected
document image — so a consumer can draw the region without also transporting the
image dimensions.

DINOv2 does not exist. Nothing was downloaded, trained or committed. What exists
is the service boundary and a mock that emits this exact contract, so everything
downstream — fusion, case assembly, storage, the officer UI — is exercised now
exactly as it will be in production.

### The eight scenarios

Reachable explicitly (tests, and **Settings → Force a screening scenario**) or
derived deterministically from the case reference:

| Scenario                       | Emits                                                    |
| ------------------------------ | -------------------------------------------------------- |
| `GENUINE`                      | `tampered: false`, no regions                            |
| `PHOTO_REPLACEMENT`            | Portrait substitution, 2 regions                         |
| `TEXT_MANIPULATION`            | Altered data field, 1 region                             |
| `STAMP_SIGNATURE_MANIPULATION` | Seal inconsistency, 1 region                             |
| `COPY_PASTE_SPLICING`          | Spliced block, 2 regions                                 |
| `UNKNOWN_MANIPULATION`         | `OTHER` with a low type score                            |
| `TAMPERED_NO_REGION`           | `PARTIAL` — classifier fired, localiser resolved nothing |
| `SERVICE_FAILURE`              | `FAILED`, `result: null`                                 |

`TAMPERED_NO_REGION` matters more than it looks. An empty region list must never
read as "nothing found", so it is reported as `PARTIAL` with a
`LOCALISATION_INCONCLUSIVE` error, and the UI states explicitly that the absence
of a highlighted region is not evidence the document is sound.

`SERVICE_FAILURE` is excluded from derived selection — an unprompted failure
would make demonstrations flaky — so it is reachable only by asking for it.

### Replacing the mock

```
MockDocumentForensicsService  →  DinoV2DocumentForensicsService
```

One line in `src/services/ai/registry.ts` (app) or the Python service registry.
No change to the risk engine, the case schema, the database, the API contract or
a single screen — because none of them names the implementation.

---

## Evidence Fusion Engine

```json
{
  "risk_score": 0.38,
  "risk_level": "HIGH",
  "contributors": [
    {
      "source": "document_forensics",
      "signal": "TAMPERED",
      "impact": "…",
      "severity": "HIGH",
      "weight": 0.4,
      "counted": true
    },
    {
      "source": "anomaly",
      "signal": "NOT_AVAILABLE",
      "impact": "…",
      "severity": "NONE",
      "weight": null,
      "counted": false
    }
  ],
  "evidence_coverage": 0.96,
  "escalations": ["Tampering was detected, which is escalated regardless…"],
  "engine_version": "evidence-fusion-1.0.0",
  "config_version": "1.0.0"
}
```

**This is not LightGBM.** It is deterministic weighted fusion, and the naming
matters: calling it LightGBM would imply the weights were fitted to labelled
fraud data when they were chosen by engineering judgement.

`risk_score` is normalised **0–1**. `risk_level` is the single officer-facing
taxonomy: **`LOW` / `REVIEW` / `HIGH`**. The four-category taxonomy in
`reference/risk-prototype/riskengine/risk.py` (Genuine / Suspicious / High-Risk Fake / Critical
Fraud) is not exposed anywhere.

### How missing evidence is handled

Modules that returned `FAILED` or `NOT_AVAILABLE` are dropped from the weighted
mean and the remaining weights are **renormalised**. A screening can never be
scored as riskier _because_ a module was down.

Note what renormalising does and does not promise. It is not monotonic in the
number of modules: dropping a module that was reporting "clean" removes positive
evidence, so the mean of what remains can sit higher than before. That is the
honest outcome — the reassurance genuinely is no longer there. The guarantee is
therefore stated as _"an absent module never scores worse than that module
reporting its worst finding"_, and tested that way.

### Why thin evidence cannot clear a case

`evidence_coverage` records how much of the configured weight was available. The
four core modules total `0.96`; requiring `0.90` means all four must have
produced evidence for a `LOW` clearance to stand, tolerating only the permanent
anomaly gap.

This is the rule that stops a case being cleared while the module that would have
caught the problem was down. **A case where tamper detection never ran is not a
low-risk case; it is an unexamined one.**

Three escalation floors do the same job for inconclusive findings — a face
`REVIEW` or a validation `REVIEW` cannot be averaged away by four quiet modules.
All of them can only _raise_ the band, never lower it.

---

## Document types

One canonical enum, snake_case, following the Python services' spelling
(`driving_license`, not `driving_licence` — the app's old spelling still parses
for stored cases).

| Type                   | OCR | Validation | MRZ |
| ---------------------- | --- | ---------- | --- |
| `passport`             | ✓   | ✓          | ✓   |
| `visa`                 | ✓   | ✓          | ✓   |
| `driving_license`      | ✓   | ✓          | —   |
| `national_id`          | ✓   | ✓          | —   |
| `permit`               | ✓   | ✓          | —   |
| `travel_authorization` | ✗   | ✗          | —   |
| `other`                | ✗   | ✗          | —   |

The last two are **kept, not deleted**. An officer meeting a document outside the
five needs somewhere to put it, and removing the option would push them into
declaring the wrong type — which runs the wrong rules and produces a confident,
wrong answer. Instead both modules return `NOT_AVAILABLE` with reason
`UNSUPPORTED_DOCUMENT_TYPE`, the capture screen says so, and `other` never
silently borrows another type's rules.

---

## Thresholds

Every band, weight and boundary lives in `contracts/config/thresholds.json`.
Python loads it via `ssb_contracts.config`; the app **imports the same file
directly** (`src/config/thresholds.ts`) — there is deliberately no hand-written
mirror to drift.

Each block carries `source` and `confidence`. Nothing in the system quotes a
number without its provenance, and the UI shows the confidence note verbatim in
analysis details. **None of these values are calibrated for production:**

- Face thresholds are LFW-calibrated (same-domain photo pairs) but used
  cross-domain (document portrait vs live capture). Provisional.
- Forensics bands are placeholders — no trained model exists.
- Fusion weights are engineering judgement, not a fit to labelled fraud data.
- The anomaly threshold is `null`, because PatchCore has not been built.

---

## Regenerating the app fixtures

The app contains no fusion, validation or decision logic. When it has no backend
it replays case documents generated by the real Python engine:

```bash
cd contracts/python
python tools/generate_screening_fixtures.py     # → src/fixtures/screening/
```

Run this after changing a threshold, a weight, or the fusion engine. Editing the
generated JSON by hand would reintroduce exactly the divergence this contract
removed.

---

## Verifying

```bash
# Python: contracts, adapters, mock DINOv2, fusion engine
cd contracts/python && python -m pytest tests -q

# TypeScript: schema parity, fixture conformance, app behaviour
npm run verify                                   # typecheck + lint + tests
npx expo export --platform android               # bundles
```
