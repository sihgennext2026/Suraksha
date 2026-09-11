# Document OCR Pipeline — FastAPI Service

End-to-end document processing: upload an image of a passport, driving license, Aadhaar card, national ID, visa, or permit and get back structured fields (name, DOB, sex, document number, nationality, etc.) as JSON.

## Pipeline Stages

1. **Orientation correction** — `PP-LCNet_x1_0_doc_ori` 4-class classifier detects 0/90/180/270 rotation and corrects it before anything else runs.
2. **Document segmentation** — U-Net/ResNet34 ONNX model produces a per-pixel mask; the document's 4 corners are extracted directly from the mask contour.
3. **Perspective correction** — Single homography warp from the 4 corners.
4. **MRZ / field region split** — Bottom band is treated as MRZ; the rest is the field region.
5. **Multilingual OCR** — PP-OCRv5 with automatic language detection. Bilingual dual-pass merge for documents with native + Latin text side by side.
6. **Structured field extraction** — MRZ decoding (ICAO 9303) for passports/visas, label/value spatial matching for all document types. Supports English, Tamil, Hindi, Chinese, French, Spanish labels.
7. **QR/barcode detection** — Detects and decodes QR codes and barcodes on the document.

## Folder Structure

```
.
├── app/
│   ├── __init__.py
│   ├── config.py              # All paths and thresholds
│   ├── detector.py            # U-Net segmentation wrapper
│   ├── field_extractor.py     # Structured field extraction
│   ├── field_labels_i18n.py   # Multilingual field label patterns
│   ├── lang_fallback.py       # Language detection + bilingual merge
│   ├── lang_map.py            # Country → OCR language mapping
│   ├── main.py                # FastAPI endpoints
│   ├── ocr.py                 # PP-OCRv5 wrapper
│   ├── orientation.py         # Orientation correction
│   ├── perspective.py         # Perspective warp
│   ├── qr_barcode.py          # QR/barcode detection
│   └── schemas.py             # Pydantic response models
├── models/
│   └── segmentation_model/
│       ├── document_detector.onnx       # U-Net model (~340 KB)
│       └── document_detector.onnx.data  # Model weights (~93 MB, Git LFS)
├── tests/
│   └── test_field_extractor.py
├── requirements.txt
├── .gitattributes             # Git LFS tracking
└── .gitignore
```

## Setup

### 1. Clone the repository

```bash
git lfs install
git clone <repo-url>
cd <repo-name>
```

**Git LFS is required** — the segmentation model weights (`document_detector.onnx.data`, 93 MB) are tracked with Git LFS. Without `git lfs install` before cloning, you'll get a pointer file instead of the actual weights.

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/Scripts/activate   # Windows (Git Bash)
# or: source venv/bin/activate # Linux/macOS
pip install -r requirements.txt
```

### 3. Start the server

```bash
source venv/Scripts/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> **Important on Windows:** Always start via `source venv/Scripts/activate && python -m uvicorn ...`. Running uvicorn directly through the venv's python.exe can cause MKL-DNN/PIR crashes.

On first startup, PaddleX auto-downloads OCR models (~280 MB total) to `~/.paddlex/official_models/`. This is a one-time cost; all subsequent runs are fully offline.

### 4. Test

Open your browser to:

```
http://127.0.0.1:8000/docs
```

Use the interactive Swagger UI: click `POST /extract` → "Try it out" → upload an image → "Execute".

Or via curl:

```bash
curl -X POST "http://127.0.0.1:8000/extract" \
  -F "file=@path/to/document.jpg" \
  -F "document_type=driving_license"
```

Add `?save_debug=true` to save intermediate images (orientation-corrected, segmented, perspective-corrected) to `api_debug_output/`.

## API Response

```json
{
  "document_type": "driving_license",
  "detected": true,
  "orientation_corrected": false,
  "correction_mode": "segmentation_quad_warp",
  "structured_fields": {
    "name": "JOHN DOE",
    "date_of_birth": "1990-05-15",
    "sex": "M",
    "document_number": "DL-1234567890",
    "nationality": "INDIAN",
    "issue_date": "2020-01-10",
    "expiry_date": "2040-01-09"
  },
  "structured_fields_sources": {
    "name": "label_same_line",
    "date_of_birth": "label_next_line",
    "nationality": "header_country"
  },
  "field_lines": ["..."],
  "timings_ms": {
    "orientation_ms": 18.4,
    "detection_ms": 60.2,
    "correction_ms": 12.8,
    "field_ocr_ms": 120.1,
    "total_ms": 283.5
  }
}
```

## Supported Document Types

| Type | MRZ Decode | Label Matching | Unlabeled Name Detection | Header Nationality |
|------|:---:|:---:|:---:|:---:|
| Passport | Yes | Yes | — | — |
| Visa | Yes | Yes | — | — |
| Driving License | — | Yes | Yes | Yes |
| National ID / Aadhaar | — | Yes | Yes | Yes |
| Permit | — | Yes | — | Yes |

## Requirements

- Python 3.9+
- PaddlePaddle 3.0+
- PaddleOCR 3.0+
- PaddleX 3.0+
- See `requirements.txt` for full list

## Hardware

Designed for CPU inference. Typical processing time: 17-45 seconds per document on a modern laptop CPU. MKL-DNN acceleration is enabled by default for ~4x speedup.
