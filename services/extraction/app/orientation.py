"""
orientation.py

WORK 1: robust 0/90/180/270 orientation detection + correction, run once
per image, BEFORE document detection / perspective correction / OCR.

BUGFIX (post-deployment, found on a real photo): confidence-thresholding
the classifier's single guess (ORIENTATION_MIN_CONFIDENCE alone) was not
enough -- a real upright Voter ID/EPIC card photo was misclassified as
"180" at confidence 0.726 (above the 0.60 threshold) and got flipped
upside down, breaking detection/OCR for that request. OrientationCorrector
.correct() now double-checks any rotation it's about to apply by
re-running the same classifier on the candidate rotated image before
committing to it -- see that method's docstring for exactly how and why
this catches this failure mode. The return signature grew a 4th value,
`applied` (bool), so callers can tell whether a rotation was actually
committed, independent of what the first pass merely guessed.

WHY THIS APPROACH (not 4 full pipeline runs, not EXIF alone):
Per the requirements this was built against: EXIF orientation can't be
trusted alone (a photo may be physically rotated, not just tagged), and
running the full detection->correction->OCR pipeline four times and
picking the highest-confidence result was explicitly ruled out as too
heavy for an offline/edge target. The right-sized tool for exactly this
job is a tiny, DEDICATED 4-class image classifier -- one cheap forward
pass, not a full OCR run.

That model already sits in this project's dependency tree, unused:
PaddleX's PP-LCNet_x1_0_doc_ori. app/ocr.py already references it
indirectly -- every PaddleOCR engine in this pipeline is built with
`use_doc_orientation_classify=False`, `use_textline_orientation=False`
because "perspective correction already ran upstream" (see ocr.py's
_build_engine). This module is what makes that comment true: it runs
that same small classifier explicitly, ONCE, before detection, instead
of leaving orientation unhandled.

VERIFIED, NOT ASSUMED -- confirmed by installing paddlex==3.7.2 and
reading its actual source (this sandbox has no network path to the
model's weight host, so the classifier's real predictions were NOT
run end-to-end here; everything below is confirmed from source, not
from output):

  - Model name "PP-LCNet_x1_0_doc_ori" is a registered image-
    classification model:
    paddlex/modules/image_classification/model_list.py
  - Its config confirms num_classes: 4 and literally uses a demo image
    named "img_rot180_demo.jpg" as its Predict.input example:
    paddlex/configs/modules/doc_text_orientation/PP-LCNet_x1_0_doc_ori.yaml
  - paddlex.create_model(name).predict(image) accepts a raw BGR numpy
    array directly -- ReadImage.read() special-cases np.ndarray input
    and does the BGR->RGB conversion itself; no temp file, no manual
    color conversion needed:
    paddlex/inference/common/reader/image_reader.py
  - The result is dict-like with "label_names" (list of strings, one of
    "0"/"90"/"180"/"270") and "scores" (top-1 confidence):
    paddlex/inference/models/image_classification/{predictor,result}.py
  - THE ROTATION-DIRECTION CONVENTION -- the one detail that's easy to
    get backwards and impossible to verify without the real weights --
    was confirmed from Paddle's OWN downstream consumer of this exact
    model, not guessed: paddlex/inference/pipelines/doc_preprocessor/
    pipeline.py takes `angle = int(pred["label_names"][0])` and calls
    `rotate_image(img, angle)`; that function (in
    paddlex/inference/pipelines/components/common/warp_image.py) feeds
    `angle` straight into `cv2.getRotationMatrix2D(center, angle, 1.0)`
    with no sign flip. OpenCV's own documented convention is that a
    POSITIVE angle there rotates COUNTER-CLOCKWISE. So label "90" means
    "rotate the image 90 degrees counter-clockwise to make it upright" --
    this module applies exactly that convention below via cv2.rotate().

STILL VERIFY ON A REAL IMAGE: this convention is inferred correctly from
Paddle's own code, but was never run end-to-end here (no network path to
the weights in this sandbox). Test with a real 90-degree-rotated photo
(see README's WORK 1 test commands) before trusting it blindly -- if a
90-degree image comes out rotated the wrong way, the fix is a one-line
swap of cv2.ROTATE_90_COUNTERCLOCKWISE <-> cv2.ROTATE_90_CLOCKWISE in
_ROTATE_FLAG_BY_LABEL below, not a redesign.

Loaded ONCE at startup (main.py's lifespan), same pattern as
DocumentDetector/DocumentOCR -- not reloaded per request.
"""
from typing import Optional, Tuple

import cv2
import numpy as np

from . import config

try:
    from paddlex import create_model
    _IMPORT_ERROR = None
except ImportError as e:  # pragma: no cover - environment-dependent
    create_model = None
    _IMPORT_ERROR = e


# Maps the classifier's label string to the cv2.rotate() flag that
# CORRECTS it -- i.e. the rotation to actually apply to make the image
# upright, given Paddle's own "positive angle = counter-clockwise"
# convention confirmed in the module docstring above.
_ROTATE_FLAG_BY_LABEL = {
    "0": None,                               # already upright, no-op
    "90": cv2.ROTATE_90_COUNTERCLOCKWISE,    # rotate 90 deg CCW to correct
    "180": cv2.ROTATE_180,
    "270": cv2.ROTATE_90_CLOCKWISE,          # rotate 270 deg CCW == 90 deg CW
}


class OrientationCorrector:
    """Loads PP-LCNet_x1_0_doc_ori once; call .correct(image_bgr) per
    request.

    See correct()'s own docstring for the full return contract
    (corrected_image, angle_label, confidence, applied) and for the
    self-consistency-check bugfix that keeps this class from acting on
    a single misclassified guess.

    Below config.ORIENTATION_MIN_CONFIDENCE, the image is returned
    UNROTATED regardless of what the classifier reported. Rationale:
    acting on a low-confidence guess risks flipping an already-upright
    document upside down, which is a worse failure mode for this
    pipeline than leaving a genuinely-rotated one uncorrected -- a
    document that's still sideways will simply fail detection/OCR
    downstream (a visible, debuggable failure), whereas a wrongly-
    flipped upright document could still produce a detection and
    plausible-looking (wrong) OCR output. (This is also, concretely,
    what the self-consistency check in correct() now catches even when
    confidence alone wasn't a high enough bar -- see that docstring.)
    """

    def __init__(self, model_name: Optional[str] = None):
        if create_model is None:
            raise ImportError(
                "paddlex is required for orientation correction but isn't "
                "importable in this environment. It's a transitive "
                "dependency of paddleocr>=3.0.0 (already in "
                "requirements.txt) -- if this still fails, check your "
                "paddleocr/paddlex install."
            ) from _IMPORT_ERROR
        self.model_name = model_name or config.ORIENTATION_MODEL_NAME
        self.model = create_model(self.model_name)

    def _classify(self, image_bgr: np.ndarray) -> Tuple[str, float]:
        """One classifier forward pass -> (label, confidence). Split out
        from correct() so the self-consistency check below (BUGFIX, see
        correct()'s docstring) can call it a second time on a candidate
        rotated image without duplicating the predict()/unpack logic."""
        result = next(iter(self.model.predict(image_bgr)))
        label = str(result["label_names"][0])
        confidence = float(result["scores"][0])
        return label, confidence

    def correct(self, image_bgr: np.ndarray) -> Tuple[np.ndarray, str, float, bool]:
        """
        BUGFIX (found on a real Tamil Nadu Voter ID / EPIC card photo that
        was already upright): the classifier called it "180" at confidence
        0.726 -- above ORIENTATION_MIN_CONFIDENCE (0.60) -- and this method
        flipped an already-correct image upside down, which then broke
        detection/OCR/every downstream stage for that request. This is
        EXACTLY the failure mode this class's own docstring already
        identified as the worse-than-leaving-it-alone outcome; 0.60 alone
        just wasn't a high enough bar to prevent it on a real image (the
        module was written and reasoned about correctly from paddlex's
        source, per the module docstring, but never run against a real
        misclassification like this one until now).

        FIX -- a self-consistency check, added ONLY on the path that's
        about to actually rotate (so the common "no rotation needed" case
        pays no extra cost): before committing to a rotation, re-run the
        SAME classifier on the CANDIDATE rotated image. If the image
        really was rotated the way the first pass said, the candidate is
        now genuinely upright and the classifier should say "0" with
        reasonable confidence again. If the first pass was a
        misclassification of an already-upright image (this bug's exact
        case), the candidate is now genuinely upside-down/sideways, which
        is an easy, high-confidence call for this classifier to get
        right -- so it will NOT say "0", and that disagreement is the
        signal to revert and leave the image as originally uploaded.
        This costs exactly one extra cheap forward pass, only when a
        rotation is actually being considered -- still lightweight enough
        for offline/edge use.

        Returns (corrected_image, angle_label, confidence, applied):
            corrected_image -- input image, rotated ONLY if (a) the first
                                pass was confident enough to act on AND
                                (b) the second pass confirmed the result.
                                Otherwise the SAME (unrotated) image
                                object.
            angle_label      -- the classifier's raw FIRST-pass label
                                ("0"/"90"/"180"/"270"), even when
                                confidence was too low to act on, or the
                                consistency check reverted it -- useful
                                for logging/debugging regardless of what
                                was actually applied.
            confidence        -- the first pass's own top-1 score, 0..1.
            applied            -- True only if a rotation was actually
                                applied to the returned image. False for
                                "already 0", "confidence too low", AND
                                "consistency check reverted it" -- callers
                                that need to know whether the returned
                                image differs from the input should check
                                this flag, not just angle_label/confidence.
        """
        if image_bgr is None or image_bgr.size == 0:
            return image_bgr, "0", 0.0, False

        label, confidence = self._classify(image_bgr)

        if confidence < config.ORIENTATION_MIN_CONFIDENCE:
            return image_bgr, label, confidence, False

        flag = _ROTATE_FLAG_BY_LABEL.get(label)
        if flag is None:  # label == "0"
            return image_bgr, label, confidence, False

        candidate = cv2.rotate(image_bgr, flag)

        verify_label, verify_confidence = self._classify(candidate)
        if verify_label != "0" or verify_confidence < config.ORIENTATION_MIN_CONFIDENCE:
            # Disagreement -- don't trust the first pass. Leave the
            # ORIGINAL image untouched rather than commit to a rotation
            # neither pass is actually confident and consistent about.
            return image_bgr, label, confidence, False

        return candidate, label, confidence, True
