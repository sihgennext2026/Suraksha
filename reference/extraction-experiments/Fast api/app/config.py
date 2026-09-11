"""
config.py

Every path and threshold the pipeline needs, in one place. Edit
PROJECT_ROOT if your folder layout differs from D:\\SIH Project --
everything else is built from it automatically.
"""
import os

PROJECT_ROOT = r"D:\\push"

# --- Stage 1: document detector (YOLOv12s, ONNX) ---
YOLO_ONNX_PATH = os.path.join(PROJECT_ROOT, "models", "document_detector", "best.onnx")
CONF_THRESHOLD = 0.25          # same value used in your evaluate_detector.py --op-conf run
NMS_IOU_THRESHOLD = 0.45
DETECTOR_INPUT_SIZE = 640      # matches the imgsz your model was trained/evaluated/exported at

# --- Stage 2: perspective correction ---
MARGIN_RATIO = 0.03            # padding around the detector box before looking for the real quad
MIN_QUAD_AREA_RATIO = 0.30
MAX_QUAD_AREA_RATIO = 0.97

# --- Stage 3: PP-OCRv5 (local inference-model folders, no internet needed) ---
PPOCR_DET_MODEL_DIR = os.path.join(
    PROJECT_ROOT, "models", "paddleocr", "PP-OCRv5_server_det_infer", "PP-OCRv5_server_det_infer"
)
PPOCR_REC_MODEL_DIR = os.path.join(
    PROJECT_ROOT, "models", "paddleocr", "PP-OCRv5_server_rec_infer", "PP-OCRv5_server_rec_infer"
)
OCR_LANG = "en"

DEVICE = "cpu"

# Where the API writes debug images (original / crop / corrected) when
# ?save_debug=true is passed to /extract. Safe to leave as-is.
DEBUG_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "api_debug_output")
