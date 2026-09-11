# Document Detection + Perspective Correction + OCR — FastAPI Service

This wraps your three working pieces into one API:

1. **Detection** — your fine-tuned `best.onnx` (YOLOv12s) finds the document.
2. **Perspective correction** — straightens it, using the same logic as your
   `step3_perspective_correction_from_detection(target).py`.
3. **OCR** — PP-OCRv5 (pretrained, no fine-tuning) reads the text, using the
   local model files you already downloaded (fully offline, no internet
   needed at runtime).

One thing worth knowing: the "PP-OCRv5 det & rec model" you downloaded is
PaddleOCR's own local model format (`inference.json` + `inference.pdiparams`
+ `inference.yml`), not ONNX. That's fine — it's still fully offline and
edge-friendly, it just runs through the `paddlepaddle` + `paddleocr`
libraries instead of `onnxruntime`. Detection still uses `onnxruntime`
separately. Two runtimes, both local, both offline.

## Folder layout this expects

```
D:\SIH Project\
    models\
        document_detector\
            best.onnx
        paddleocr\
            PP-OCRv5_server_det_infer\PP-OCRv5_server_det_infer\
                inference.json, inference.pdiparams, inference.yml
            PP-OCRv5_server_rec_infer\PP-OCRv5_server_rec_infer\
                inference.json, inference.pdiparams, inference.yml
    document_ocr_api\        <- put these files here
        app\
            __init__.py, config.py, detector.py, perspective.py,
            ocr.py, schemas.py, main.py
        requirements.txt
```

If your paths differ, the only file you need to edit is `app/config.py` —
everything else reads from there.

## Step 1 — Put the files in place

Create the folder `D:\SIH Project\document_ocr_api\app\` and put all the
`.py` files there, plus `requirements.txt` one level up in
`D:\SIH Project\document_ocr_api\`.

## Step 2 — Install dependencies

Open a terminal in `D:\SIH Project\document_ocr_api` and run:

```cmd
pip install -r requirements.txt
```

This will take a few minutes the first time (paddlepaddle is a large
download).

## Step 3 — Start the server

Still in `D:\SIH Project\document_ocr_api`, run:

```cmd
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Wait for these lines — they mean both models loaded successfully:

```
Loading document detector (best.onnx) ...
Loading PP-OCRv5 (local model files, offline) ...
Models loaded. Ready.
```

Leave this window open — it's your running server.

## Step 4 — Test it

**Easiest way:** open your browser to

```
http://127.0.0.1:8000/docs
```

This shows an interactive page. Click `POST /extract` → "Try it out" →
choose an image file → "Execute". You'll get back the recognized text,
confidence scores, and timing, right in the browser.

**Or from a second terminal**, using curl:

```cmd
curl -X POST "http://127.0.0.1:8000/extract" -F "file=@D:\SIH Project\data\midv500_yolo\images\test\SOME_IMAGE.jpg"
```

(Replace the path with a real test image on your machine.)

**To also save the intermediate images** (original / corrected) so you can
see what the pipeline actually did, add `?save_debug=true` to the URL:

```
http://127.0.0.1:8000/extract?save_debug=true
```

Saved images land in `D:\SIH Project\api_debug_output\`.

## What you get back

```json
{
  "detected": true,
  "detection_confidence": 0.94,
  "detection_box": [120.3, 80.1, 540.7, 610.9],
  "correction_mode": "cv_contour_warp",
  "lines": [
    {"text": "REPUBLIC OF ALBANIA", "confidence": 0.98},
    {"text": "IDENTITY CARD", "confidence": 0.95}
  ],
  "full_text": "REPUBLIC OF ALBANIA IDENTITY CARD ...",
  "average_confidence": 0.96,
  "timings_ms": {
    "detection_ms": 145.2,
    "correction_ms": 12.8,
    "ocr_ms": 210.4,
    "total_ms": 368.4
  }
}
```

`correction_mode` tells you which path was used:
- `"cv_contour_warp"` — a clean 4-corner document outline was found and
  straightened.
- `"fallback_axis_aligned_crop"` — no clean outline was found (busy
  background, low contrast), so it just used the plain rectangular crop
  from the detector, unwarped.

If no document was found at all, you'll get `"detected": false` and a
message, instead of an error.

## Stopping the server

Go back to the terminal running `uvicorn` and press `Ctrl+C`.
