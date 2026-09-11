"""
config.py

Every path and threshold the pipeline needs, in one place.
PROJECT_ROOT is auto-detected as the repo root (the directory containing
this app/ package). All other paths are built from it automatically.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Stage 0: orientation detection + correction (WORK 1) ---
# See app/orientation.py's module docstring for exactly how the model
# name, its I/O contract, and the rotation-direction convention below
# were confirmed by reading paddlex 3.7.2's installed source -- not
# guessed. Runs once, on the full original photo, before detection.
ORIENTATION_MODEL_NAME = "PP-LCNet_x1_0_doc_ori"
# Below this top-1 confidence, the classifier's guess is ignored and the
# image is left unrotated -- see OrientationCorrector.correct()'s
# docstring for why "do nothing" is the safer failure mode here than
# "act on a low-confidence guess".
ORIENTATION_MIN_CONFIDENCE = 0.60

# --- Stage 1: document detector (U-Net/ResNet34 segmentation, ONNX) ---
# Replaces the old YOLOv12s bounding-box detector. This model outputs a
# per-pixel document-probability mask instead of a box, so the pipeline
# gets the document's actual 4 corners directly from the mask contour --
# see app/detector.py. document_detector.onnx.data (external tensor data)
# must sit alongside document_detector.onnx in the same folder; onnxruntime
# resolves it automatically via the relative path baked into the .onnx file.
SEGMENTATION_ONNX_PATH = os.path.join(PROJECT_ROOT, "models", "segmentation_model", "document_detector.onnx")
SEGMENTATION_INPUT_SIZE = 512   # matches the model's trained/exported input resolution
SEGMENTATION_THRESHOLD = 0.5    # sigmoid probability cutoff for the binary mask

# Morphological cleanup applied to the binary mask before contour-finding
# (fills small holes inside the document, then strips small noise blobs).
SEGMENTATION_MORPH_KERNEL_SIZE = 5
SEGMENTATION_MORPH_CLOSE_ITERATIONS = 2
SEGMENTATION_MORPH_OPEN_ITERATIONS = 1

# Smallest contour area (as a fraction of the 512x512 mask) that's still
# plausibly a document, not noise. Below this, detect() returns None --
# the segmentation equivalent of "no detection above confidence threshold".
SEGMENTATION_MIN_CONTOUR_AREA_RATIO = 0.02

# Corner extraction: approxPolyDP is swept across a range of epsilon
# factors looking for one that collapses the contour to exactly 4 points
# (far more robust than a single fixed epsilon); falls back to
# cv2.minAreaRect() if none in the sweep lands on exactly 4.
SEGMENTATION_CORNER_EPSILON_MIN = 0.005
SEGMENTATION_CORNER_EPSILON_MAX = 0.05
SEGMENTATION_CORNER_EPSILON_STEPS = 40

# --- Stage 2: perspective correction ---
# The segmentation model already hands back the document's real 4
# corners (see above), so correction is a single homography warp -- no
# crop-then-search-for-corners heuristics needed the way the old YOLO
# bounding box required. MIN_QUAD_AREA_RATIO is only a sanity check: if
# the reported quad is implausibly tiny relative to the full image,
# correct_from_quad() falls back to an uncorrected axis-aligned crop
# instead of trusting a degenerate warp.
MIN_QUAD_AREA_RATIO = 0.02

# --- Stage 2c: MRZ / field region split ---
# Bottom fraction of the corrected image treated as the MRZ band. Tuned
# for TD3 (passport) layouts -- may need adjusting per document type
# (e.g. TD1 ID cards place the MRZ differently relative to card height).
# NOTE: this ratio assumes the corrected image tightly bounds the
# document. That holds for "segmentation_quad_warp" but NOT for
# "fallback_axis_aligned_crop" -- check correction_mode in the response
# if MRZ/field splitting looks off for a given document.
MRZ_CROP_RATIO = 0.20

# --- Stage 3: PP-OCRv5 ---
# OCR models are loaded by name via PaddleOCR/PaddleX and auto-download
# to ~/.paddlex/official_models/ on first use. No local model folders needed.
OCR_LANG = "en"

DEVICE = "cpu"

# --- Stage 3c: field-language fallback chain (app/lang_fallback.py) ---
# Only exercised when MRZ is absent or fails format validation -- driving
# licenses, IDPs, many visas, and non-ICAO national IDs like Aadhaar.
HEADER_CROP_RATIO = 0.18          # top fraction of the field region treated as the "header" band
MRZ_CHAR_VALIDITY_RATIO = 0.90    # fraction of chars that must be A-Z/0-9/< to trust MRZ as a language signal
MRZ_LINE_LENGTH_TOLERANCE = 2     # +/- chars allowed vs canonical TD1/TD2/TD3 line widths
CONFIDENCE_RACE_EARLY_EXIT = 0.90     # stop racing once a candidate clears this mean confidence
CONFIDENCE_RACE_MIN_ACCEPT = 0.55     # below this even the "winner" isn't trusted -> default fallback
CONFIDENCE_RACE_MAX_CANDIDATES = 6    # bounds worst-case latency when both MRZ and header fail --
                                       # candidates are tried in lang_map.ALL_LANG_FAMILIES order
                                       # (Latin first), so this caps how many *unlikely* scripts get
                                       # tried before giving up and falling to the default. Raise this
                                       # (or set to None for no cap) once you've measured how slow a
                                       # full race actually is on your hardware.

# --- Stage 3d: bilingual dual-pass merge (app/lang_fallback.run_field_ocr) ---
# Driving licenses, Aadhaar, and many national IDs print native script
# and Latin/English side by side -- a single "winning" language always
# loses whichever script it didn't cover. When the resolved language
# isn't already DEFAULT_LANG, a second Latin-family pass is run over the
# same field-region crop and merged in by bounding-box overlap.
DUAL_PASS_ENABLED = True
DUAL_PASS_IOU_THRESHOLD = 0.5   # overlap fraction above which two passes' boxes count as "same line"

# --- QR/barcode detection + cropping (WORK 5) ---
# Pixel margin added around every QR/barcode crop to preserve the quiet
# zone and give downstream decoders room to work.
QR_BARCODE_CROP_MARGIN = 20
# Base directory for QR/barcode crop outputs, organized per-request as
# <base>/<side>/qr_barcode/
QR_BARCODE_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "qr_barcode_output")

# Where the API writes debug images (original / crop / corrected) when
# ?save_debug=true is passed to /extract. Safe to leave as-is.
DEBUG_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "api_debug_output")
