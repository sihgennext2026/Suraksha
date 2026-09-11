# Document OCR Field Extraction, Evaluation & Validation Service

**Terminal + backend only** — no frontend, no browser UI.

## How to run

```bash
cd document_validation_service
pip install -r requirements.txt

python evaluate.py
```

The program asks:

```
Enter document type:
  1. passport
  2. driving_license
  3. visa
  4. national_id
  5. permit

Enter document type: driving_license

Enter OCR JSON file path: evaluation_data/driving_license/case_001_ocr.json
```

Then it:

1. Reads the **raw OCR JSON** file  
2. Extracts fields with the document-specific extractor  
3. Compares against expected ground truth in `evaluation_data/`  
4. Calculates score  
5. Saves JSON under `results/`

### Non-interactive

```bash
# One OCR file
python evaluate.py --document-type driving_license \
  --ocr-file evaluation_data/driving_license/case_001_ocr.json

# All cases for a type
python evaluate.py --document-type driving_license --all-cases
```

## Input

- **Document type** — you must provide it (never auto-detected)  
- **OCR file** — path to a **raw OCR JSON** file (`lines`, `full_text`, confidences, …)

Do **not** pass structured field JSON as input.

## Output

Terminal shows a short summary. Full result is saved as:

```
results/driving_license_evaluation.json
```

Format:

```json
{
  "document_type": "driving_license",
  "evaluation": {
    "total_cases": 1,
    "passed_cases": 1,
    "failed_cases": 0,
    "review_cases": 0,
    "score": 100.0,
    "score_percent": 100.0,
    "overall_status": "PASS"
  },
  "failed_cases": []
}
```

Failed cases include field-level reasons only (no detailed passed-case listings).

## Optional API server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Docs: http://localhost:8000/docs
```

## Project layout

```
document_validation_service/
├── app/                  # extractors, evaluation, validators, rules
├── evaluation_data/      # raw OCR + expected pairs per document type
├── results/              # evaluation JSON outputs
├── tests/
├── evaluate.py           # terminal entry point
├── requirements.txt
└── README.md
```

No `frontend/`, no HTML/CSS/JS UI.
