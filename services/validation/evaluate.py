#!/usr/bin/env python3
"""
Terminal-driven evaluation — no frontend.

Interactive:
  python evaluate.py

  Enter document type: driving_license
  Enter OCR JSON file path: evaluation_data/driving_license/case_001_ocr.json

Non-interactive:
  python evaluate.py --document-type driving_license --ocr-file path/to/ocr.json
  python evaluate.py --document-type driving_license --all-cases

Reads RAW OCR JSON from the given file path, extracts fields, evaluates against
expected ground truth from evaluation_data/, saves JSON under results/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evaluation.case_evaluator import CaseBasedEvaluator

SUPPORTED = [
    "passport",
    "driving_license",
    "visa",
    "national_id",
    "permit",
]

EVAL_DIR = ROOT / "evaluation_data"
RESULTS_DIR = ROOT / "results"


def prompt_document_type() -> str:
    print()
    print("Enter document type:")
    print("  1. passport")
    print("  2. driving_license")
    print("  3. visa")
    print("  4. national_id")
    print("  5. permit")
    print()
    while True:
        raw = input("Enter document type: ").strip().lower()
        if not raw:
            print("  Document type is required.")
            continue
        mapping = {
            "1": "passport",
            "2": "driving_license",
            "3": "visa",
            "4": "national_id",
            "5": "permit",
        }
        if raw in mapping:
            return mapping[raw]
        if raw in SUPPORTED:
            return raw
        print(f"  Unsupported type '{raw}'. Choose one of: {', '.join(SUPPORTED)}")


def prompt_ocr_path() -> Path:
    print()
    while True:
        raw = input("Enter OCR JSON file path: ").strip().strip('"').strip("'")
        if not raw:
            print("  OCR JSON file path is required.")
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            alt = (ROOT / raw).resolve()
            if alt.exists():
                path = alt
            else:
                print(f"  File not found: {raw}")
                continue
        if not path.is_file():
            print(f"  Not a file: {path}")
            continue
        return path


def load_ocr_json(path: Path) -> dict:
    print("Reading OCR JSON...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("OCR JSON must be an object")
    if "lines" not in data and "full_text" not in data:
        raise ValueError(
            "OCR JSON does not look like raw OCR (missing 'lines' / 'full_text'). "
            "Do not pass structured field JSON as input."
        )
    return data


def resolve_expected(document_type: str, ocr_path: Path) -> tuple:
    """
    Load expected ground truth for this OCR file.
    Prefer matching case_XXX_expected.json if OCR filename is case_XXX_ocr.json;
    otherwise fall back to case_001_expected.json.
    """
    type_dir = EVAL_DIR / document_type
    stem = ocr_path.stem
    case_id = "adhoc"

    m = re.match(r"(case_\d+)_ocr$", stem, re.IGNORECASE)
    if m:
        case_id = m.group(1)
        exp_path = type_dir / f"{case_id}_expected.json"
        if exp_path.exists():
            with open(exp_path, "r", encoding="utf-8") as f:
                return json.load(f), case_id

    exp_path = type_dir / "case_001_expected.json"
    if exp_path.exists():
        with open(exp_path, "r", encoding="utf-8") as f:
            return json.load(f), case_id if case_id != "adhoc" else "case_001"

    raise FileNotFoundError(
        f"No expected JSON found under evaluation_data/{document_type}/. "
        f"Need at least case_001_expected.json"
    )


def evaluate_single_file(document_type: str, ocr_path: Path) -> dict:
    """Run extraction + evaluation for one raw OCR file."""
    ocr = load_ocr_json(ocr_path)
    expected, case_id = resolve_expected(document_type, ocr_path)

    print("Extracting document fields...")
    print("Evaluating fields...")
    print("Calculating score...")

    evaluator = CaseBasedEvaluator(EVAL_DIR)
    case_result = evaluator.evaluate_single_ocr(
        document_type=document_type,
        ocr=ocr,
        expected=expected,
        case_id=case_id,
    )

    case_score = case_result["case_score"]
    case_status = case_result["case_status"]
    failed_fields = case_result.get("failed_fields") or []

    passed = 1 if case_status == "PASS" else 0
    failed = 1 if case_status == "FAIL" else 0
    review = 1 if case_status == "REVIEW" else 0

    overall_status = CaseBasedEvaluator(EVAL_DIR)._score_to_status(case_score)

    result = {
        "document_type": document_type,
        "input_file": str(ocr_path),
        "evaluation": {
            "total_cases": 1,
            "passed_cases": passed,
            "failed_cases": failed,
            "review_cases": review,
            "score": case_score,
            "score_percent": case_score,
            "overall_status": overall_status,
        },
        "failed_cases": [],
        "review_cases": [],
    }

    detail = {
        "case_id": case_id,
        "case_score": case_score,
        "failed_fields": failed_fields,
    }
    if case_status == "FAIL":
        result["failed_cases"].append(detail)
    elif case_status == "REVIEW":
        result["review_cases"].append(detail)

    return result


def evaluate_all_cases(document_type: str) -> dict:
    """Evaluate every case under evaluation_data/<document_type>/."""
    print("Loading all evaluation cases...")
    print("Extracting document fields...")
    print("Evaluating fields...")
    print("Calculating score...")
    evaluator = CaseBasedEvaluator(EVAL_DIR)
    return evaluator.evaluate_document_type(document_type)


def save_result(document_type: str, result: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    primary = RESULTS_DIR / f"{document_type}_evaluation.json"
    stamped = RESULTS_DIR / f"{document_type}_evaluation_{ts}.json"
    with open(primary, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    with open(stamped, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return primary


def print_summary(result: dict, ocr_path=None) -> None:
    doc = result.get("document_type", "?").replace("_", " ").upper()
    ev = result.get("evaluation") or {}
    print()
    print("=" * 40)
    print("DOCUMENT EVALUATION")
    print("=" * 40)
    print()
    print(f"Document Type : {doc}")
    if ocr_path:
        print(f"Input File    : {ocr_path}")
    print()
    print(f"Total Cases   : {ev.get('total_cases', 0)}")
    print(f"Passed Cases  : {ev.get('passed_cases', 0)}")
    print(f"Failed Cases  : {ev.get('failed_cases', 0)}")
    print(f"Review Cases  : {ev.get('review_cases', 0)}")
    print()
    print(f"Score         : {ev.get('score_percent', 0):.2f}%")
    print(f"Status        : {ev.get('overall_status', '?')}")
    print()
    failed = result.get("failed_cases") or []
    review = result.get("review_cases") or []
    if failed:
        print(f"Failed Cases  : {len(failed)}")
        for case in failed:
            print(f"  {case.get('case_id')} (score: {case.get('case_score')}%)")
            for ff in case.get("failed_fields") or []:
                print(f"    - {ff.get('field')}: {ff.get('reason')}")
        print()
    if review:
        print(f"Review Cases  : {len(review)}")
        for case in review:
            print(f"  {case.get('case_id')} (score: {case.get('case_score')}%)")
            for ff in case.get("failed_fields") or []:
                print(f"    - {ff.get('field')}: {ff.get('reason')}")
        print()
    out = result.get("result_file") or f"results/{result.get('document_type')}_evaluation.json"
    print("Output saved to:")
    print(f"  {out}")
    print("=" * 40)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate raw OCR JSON (terminal input → JSON result file)"
    )
    parser.add_argument(
        "--document-type",
        "-d",
        choices=SUPPORTED,
        help="Document type (skip interactive prompt)",
    )
    parser.add_argument(
        "--ocr-file",
        "-f",
        help="Path to raw OCR JSON file (skip interactive prompt)",
    )
    parser.add_argument(
        "--all-cases",
        action="store_true",
        help="Evaluate all cases in evaluation_data/<type>/",
    )
    args = parser.parse_args()

    if args.document_type:
        document_type = args.document_type
    else:
        document_type = prompt_document_type()

    ocr_path = None
    if args.all_cases:
        result = evaluate_all_cases(document_type)
        input_display = None
    elif args.ocr_file:
        ocr_path = Path(args.ocr_file)
        if not ocr_path.is_absolute():
            ocr_path = (Path.cwd() / ocr_path).resolve()
        if not ocr_path.exists():
            alt = (ROOT / args.ocr_file).resolve()
            if alt.exists():
                ocr_path = alt
            else:
                print(f"Error: OCR file not found: {args.ocr_file}", file=sys.stderr)
                return 1
        result = evaluate_single_file(document_type, ocr_path)
        input_display = str(ocr_path)
    else:
        ocr_path = prompt_ocr_path()
        result = evaluate_single_file(document_type, ocr_path)
        input_display = str(ocr_path)

    print("Generating result...")
    out_path = save_result(document_type, result)
    result["result_file"] = str(out_path.relative_to(ROOT))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("Evaluation completed.")
    print_summary(result, input_display)

    status = (result.get("evaluation") or {}).get("overall_status", "FAIL")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
