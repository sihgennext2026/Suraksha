# Screening service

Runs the real screening modules and returns the canonical case document the
officer application renders. One endpoint does the whole case:

```
POST /screen    case_id, document_type, document (file), person (file)
GET  /health    which modules can currently produce evidence
```

## What actually runs

```
capture
  → orientation classification         PP-LCNet_x1_0_doc_ori
  → document detection                 document_detector.onnx (U-Net segmentation)
  → perspective correction             homography warp from the mask's 4 corners
  → MRZ band / field region split      passport and visa only
  → text recognition                   PP-OCRv5, language resolved per document
  → MRZ decode + field extraction      services/extraction/app/field_extractor.py
  → QR / barcode                       zxing-cpp, OpenCV fallback
  → rule validation                    services/validation deterministic rule sets
  → document portrait extraction       SCRFD
  → five-point alignment               faceverify/alignment.py
  → face embedding                     ArcFace R50 (buffalo_m/w600k_r50.onnx)
  → cosine similarity + decision       thresholds from contracts/config/thresholds.json
  → evidence fusion                    ssb_contracts EvidenceFusionEngine
```

Two modules are absent and are reported `NOT_AVAILABLE` on every case:

| Module | Why |
| --- | --- |
| Document forensics | DINOv2 is not implemented — no model, no weights, no training data. The mock in `ssb_contracts.services.forensics_mock` is left untouched and is deliberately **not** called here. |
| Anomaly detection | PatchCore was never built. |

`NOT_AVAILABLE` is an absence of evidence, never a finding. The fusion engine
does not score it, and because tamper detection carries the largest weight, a
document that is otherwise clean still lands at `REVIEW` rather than `LOW`. That
is the intended behaviour: nothing has examined it for tampering.

## Running it

```powershell
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File run.ps1
```

`run.ps1` prints the addresses the phone can use. Put one of them into the app
under **Settings → Screening service**. Models load at startup and the first
launch downloads the PP-OCRv5 language families, which takes a few minutes; they
are cached in `~/.paddlex` afterwards.

### Two environment details the launcher handles

- **TLS.** Antivirus HTTPS scanning (Avast, Kaspersky, corporate proxies)
  presents a certificate signed by a private CA. PaddleX fetches its language
  models over HTTPS and fails with `CERTIFICATE_VERIFY_FAILED` unless Python is
  told to trust it. Node already knows about it through `NODE_EXTRA_CA_CERTS`;
  Python has no equivalent, so the launcher builds a bundle from certifi's roots
  plus that CA. Trust is widened by exactly the CA already installed on the
  machine, never disabled.
- **The model-source probe.** PaddleX pings several model hosts at startup and
  aborts if none answer, turning a slow network into a failed launch. The probe
  is skipped; a model that is genuinely missing still fails when it is needed.

### paddlepaddle is pinned

`paddlepaddle==3.0.0`, not `>=3.0.0`. Version 3.3.1 raises

```
NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]   (onednn_instruction.cc:118)
```

on the first inference of the orientation model. Neither `FLAGS_use_mkldnn=0`
nor `FLAGS_enable_pir_api=0` avoids it, because PaddleX sets the predictor's
oneDNN option itself. 3.0.0 runs the same graphs correctly.

## How the three services are loaded

`services/extraction` and `services/validation` both ship a top-level package
named `app`, so they cannot both be on `sys.path` — whichever lands in `sys.modules` first wins
and the other's submodules silently resolve against it.
[`loader.py`](ssb_screening_api/loader.py) binds the extraction package under the alias
`extraction_service`, which is safe because it uses relative imports throughout,
and leaves
`services/validation` the real name, which it needs because its imports are
absolute.

## Where policy lives

Nothing in this service decides what evidence means. It sequences the pipelines,
hands each result to the adapter in `ssb_contracts.adapters` that expresses it as
an `Envelope`, and calls `ssb_contracts.assemble` to fuse them. Thresholds come
from `contracts/config/thresholds.json`, which Python and the app both read, so
there is one definition of a match, a review band and a risk boundary.

The one piece of translation this service does own is the field-name mapping in
[`pipeline.py`](ssb_screening_api/pipeline.py): the extraction service and the validation rule
sets were written independently and name the same things differently
(`document_number` against `passport_number`, `issue_date` against
`date_of_issue`). Every entry there is a synonym. None derives, combines or
reinterprets a value.

## Known gaps

- **Field coverage.** The extraction service has no schema for `visa_type`, `permit_type`,
  `place_of_birth`, `blood_group`, `license_class`, `employer` and similar. Rule
  sets that require them will report them missing, which is accurate — the
  pipeline did not read them — but it means visas and permits currently cannot
  reach a fully valid result.
- **`date_of_issue` on passports.** The MRZ does not carry it, so it is found
  only when label matching locates it on the visible page.
- **Off-device inference.** The models need a host runtime, so screening
  requires this service to be reachable. Everything either side of inference —
  capture, the case record, the officer's decision, the audit trail and the sync
  queue — is local, so a screened case stays fully usable with no network.

## TODO(production)

- Mutual TLS between the app and this service; a capture currently crosses the
  post's network unencrypted.
- Provision the address through device management rather than app settings.
- Calibrate the face thresholds on document-to-live pairs. The current values
  come from LFW and are provisional for this cross-domain use.
