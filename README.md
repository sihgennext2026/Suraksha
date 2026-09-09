# SSB Suraksha

Officer-facing field application for the **SSB26188 AI-Based Fake Identity & Document Screening System**.

An SSB officer at a border post uses this application to screen an identity or travel document and
the person presenting it: capture the document, capture the subject, run an eight-stage screening on
the device, review the evidence, and record an operational decision. It is built to work with no
network at all — connectivity only determines _when_ a completed case leaves the device, never
whether a screening can be performed.

This build is **frontend-first**. There is no backend and no real inference yet. Every model is
stood in for by a deterministic mock behind the same typed interface the production implementation
will satisfy, so replacing them is a change to one registry function rather than a rewrite.

---

## Stack

Expo SDK 54 · React Native 0.81 · React 19.1 · TypeScript 5.9 (strict) · Expo Router 6 ·
Zustand · TanStack Query · React Hook Form + Zod · expo-sqlite · expo-secure-store ·
Reanimated 4 · Gesture Handler · FlashList 2.

## Running it

```bash
npm install
npm start          # then press "a" for Android, "i" for iOS, or scan the QR code
```

The screening flow needs a camera. On a simulator, use the **import an image** control on the
document capture screen; the subject capture step requires a real device or a simulated camera.

### Demonstration sign-in

Three officers are enrolled on a fresh device, one per permission level. The login screen lists
them behind **Show** and fills the form when one is tapped.

| Officer ID | PIN    | Role          |
| ---------- | ------ | ------------- |
| `SSB4471`  | `4471` | Officer       |
| `SSB2210`  | `2210` | Supervisor    |
| `SSB1000`  | `1000` | Administrator |

PINs are hashed with a per-record salt before anything is written to storage; the plaintext exists
only in the seed list that provisions the device.

### Scripts

| Command             | What it does                          |
| ------------------- | ------------------------------------- |
| `npm start`         | Expo dev server                       |
| `npm run typecheck` | `tsc --noEmit`, strict mode           |
| `npm run lint`      | ESLint, zero warnings allowed         |
| `npm test`          | Jest suite                            |
| `npm run verify`    | Typecheck, lint and tests in sequence |
| `npm run format`    | Prettier                              |

---

## What an officer does

```
Sign in ──▶ Operations ──▶ New screening
                              │
                              ├─ 1  Declare the document type
                              ├─ 2  Capture the document
                              ├─ 3  Review the capture
                              ├─ 4  Capture the subject
                              └─ 5  Screening runs
                                     │
                                     ├─ Document detection      YOLOv8-doc
                                     ├─ Document processing     rectification
                                     ├─ OCR and MRZ             TrOCR + MRZ reader
                                     ├─ Rule validation         deterministic engine
                                     ├─ Face verification       ArcFace R50
                                     ├─ Document forensics      DINOv2 ViT-B/14
                                     ├─ Anomaly analysis        PatchCore
                                     └─ Risk assessment         LightGBM
                                     │
                              Result ──▶ Evidence ──▶ Officer decision
                                                          │
                                              Saved locally ──▶ Sync queue ──▶ Uploaded
```

Two rules shape the whole design:

- **The officer declares the document type.** Nothing infers it. That selection chooses the rule
  set, the expected machine-readable zone format, and the reference distribution the anomaly
  detector measures against — a model that quietly mis-classified a document would change all three
  without anyone noticing.
- **The system assesses; the officer decides.** The risk screen never issues an operational verdict,
  the recommendation is never pre-selected on the decision screen, and a decision that diverges from
  the recommendation is recorded as a first-class outcome rather than treated as an error.

---

## Architecture

Feature-based. Domain logic never lives in a component, and no screen ever touches SQL or names a
mock class.

```
app/                        Expo Router routes — thin, they re-export a screen
src/
  components/               Design-system components (primitives, layout, data, feedback, overlay)
  constants/                Labels, thresholds, routes, storage keys
  db/                       SQLite: migrations, row types, repositories
  features/                 auth · dashboard · screening · document · face · ocr ·
                            validation · forensics · anomaly · risk · evidence ·
                            decision · cases · settings
  fixtures/                 Authored screening scenarios + their schema
  hooks/                    Cross-feature hooks
  services/
    ai/                     Service interfaces + the implementation registry
    api/                    Authentication
    mock/                   Deterministic stand-ins for the models
    storage/                Key/value, secure, and media storage
    sync/                   Remote API interface + the sync worker
  stores/                   Zustand stores (auth, screening, settings, connectivity)
  theme/                    Tokens, palettes, ThemeProvider
  types/                    Domain model
  utils/                    Formatting, masking, dates, seeded randomness, logging
```

### Service contracts

Every module result crosses one canonical boundary, defined once in
`contracts/schemas/ssb-screening.schema.json` and mirrored in Python
(`contracts/python/ssb_contracts/`) and TypeScript (`src/contracts/`). See
**[contracts/README.md](contracts/README.md)** for the full contract
documentation and the integration status table.

The application holds **no inference logic**. It does not classify a face
comparison, evaluate a validation rule, or fuse a risk score — it renders the
case document a service returned. `getScreeningService()` in
`src/services/ai/registry.ts` is the single place that binds the service
interfaces to an implementation.

Two things follow from that, and they are the point of the arrangement:

- Swapping the mock tamper detector for the real DINOv2 model changes one line
  and nothing else — not the risk engine, not the database, not a screen.
- When the app has no backend it replays case documents **generated by the real
  Python engine** (`src/fixtures/screening/`), rather than computing its own.
  There is no second implementation to drift.

### Determinism

A case's scenario, its per-stage latency and its sync outcome are all derived
from the case reference, so a given case replays identically across runs and
restarts. That is what makes a demonstration rehearsable and a defect
reproducible.

Ten generated scenarios ship in `src/fixtures/screening/`, covering every module
state the interface has to render — a clean screening, each face decision, a
tampered document, a tampered document whose region could not be localised, a
failed module, an unsupported document type, and a screening where nothing ran
at all. Regenerate them with:

```bash
cd contracts/python && python tools/generate_screening_fixtures.py
```

---

## Offline-first

Everything an officer does at the counter works with no network:

- Sign-in verifies against an enrolment record held in secure storage on the device.
- The case row is written to SQLite the moment a case is opened, before any capture — an
  interruption loses nothing, and every audit event can reference a real case from the first moment.
- All eight screening stages run on the device.
- The decision is recorded locally; the case is then queued for upload.

`src/services/sync/syncEngine.ts` drains that queue when connectivity allows. Ordering is
deliberate: the queue entry is marked in-flight _before_ the request, the case is marked synced only
_after_ the server acknowledges it, and a failure schedules a backoff without removing anything
locally. Entries stranded by a crash are recovered to pending at startup, and `case_id` carries a
UNIQUE constraint so duplicate prevention is structural rather than a race the worker has to win.

Settings → Diagnostics can force any pipeline stage to fail, so the recovery paths can be exercised
on real hardware rather than only asserted in tests.

---

## Design

A restrained operational language rather than a dashboard: tight radii, hairline borders, generous
spacing, monospaced data values so document numbers and MRZ lines can be read back character by
character. Cards are reserved for content that is genuinely a discrete object; most grouping is done
with a label and whitespace.

Colour carries four meanings only — pass, review, failure, information — and it never carries a
meaning alone. Every status resolves to a **label, a glyph, and an accessible announcement** as well
as a colour, which is what keeps the interface readable in direct sunlight, in greyscale, and with a
colour vision deficiency. Both light and dark themes ship; dark is the default for night work at a
post.

---

## Testing

**198 tests**: 135 in the application across 6 suites, plus 63 Python contract
tests covering the envelope, the adapters, the mock DINOv2 and the fusion engine.

```bash
npm run verify                                   # app: typecheck, lint, tests
cd contracts/python && python -m pytest tests -q # services and contracts
```

| Suite               | Covers                                                                              |
| ------------------- | ----------------------------------------------------------------------------------- |
| `contracts.test.ts` | Schema parity, threshold sourcing, and conformance of every generated fixture       |
| `repositories.test` | The real migration and SQL, against Node's own SQLite engine                        |
| `sync.test.ts`      | Upload ordering, backoff, duplicate prevention, offline as a no-op                  |
| `workflow.test.ts`  | Sign-in → capture → screen → decide → save offline → sync, plus both recovery paths |
| `screens.test.tsx`  | Login and document-type screens; status accessibility; error and empty states       |
| `utils.test.ts`     | Masking, formatting, dates, seeded determinism, error sanitisation                  |

Repository tests run against a real SQLite engine via `__tests__/support/sqliteTestDatabase.ts`, so
the schema, the upsert conflict clauses, and the cascade deletes are genuinely executed rather than
asserted against a hand-written fake.

---

## Security

This is a prototype. What is already in place:

- No secrets in the repository; no plaintext credentials stored.
- Session, device identity and the credential verifier live in `expo-secure-store`, written with
  `WHEN_UNLOCKED_THIS_DEVICE_ONLY`.
- `src/utils/logger.ts` redacts by key and drops anything that looks like a file URI, so names,
  document numbers and capture paths cannot reach a log sink.
- Document numbers are masked everywhere except the OCR screen an officer opened deliberately.
- Sign-in failures return identical wording whether the officer ID or the PIN was wrong, so the
  screen cannot be used to enumerate valid officer IDs.
- No case data is transmitted during screening. Upload happens once, to the central case service.

Marked `TODO(production)` in the code:

- Replace SHA-256 with a memory-hard KDF (Argon2id) for the PIN verifier.
- Encrypt the case media container with a key held in the platform keystore.
- Provision and revoke enrolment records through the device management service, with an expiry that
  forces periodic online re-authentication.
- Add a failed-attempt lockout backed by a clock the officer cannot reset.
- Implement the retention schedule that purges cases and their audit trails.
