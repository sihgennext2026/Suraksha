"""
Adapter: gowtham-pepline face verification -> canonical contract.

The upstream pipeline lives in its own repository and is not modified. It
returns a `VerificationResult` carrying a raw cosine similarity, a three-way
decision, and two `QualityResult` objects. This module maps that onto the
canonical envelope, and does so by duck typing rather than by importing the
package, so the contracts package stays importable on a machine that has no
ONNX runtime and no 166 MB of ArcFace weights.

The one thing this adapter deliberately does NOT do is manufacture a quality
score. `QualityResult` reports pass/fail gates plus raw measurements - blur,
brightness, a yaw proxy - and no single 0..1 figure. Compressing those into one
number would be an invented confidence, so `quality.score` stays null and the
real measurements are carried through instead.
"""

from __future__ import annotations

from typing import Any, Optional

from ..config import Thresholds, load as load_thresholds
from ..core import Envelope, Module, ModuleError, failed, success
from ..modules import (
    FaceDecision,
    FaceQuality,
    FaceQualityChecks,
    FaceQualityMetrics,
    FaceThresholdsPayload,
    FaceVerificationResult,
)

#: Recorded against every case so a later re-tuning cannot silently change what
#: an officer was shown. Mirrors gowtham-pepline's model files.
ARCFACE_MODEL_VERSION = "arcface-r50-buffalo_m-w600k"


def _quality_from(raw: Any) -> FaceQuality:
    """Maps a `QualityResult`-shaped object. Tolerates None and partial objects."""
    if raw is None:
        return FaceQuality(acceptable=None, score=None)

    def get(name: str) -> Any:
        return getattr(raw, name, None)

    return FaceQuality(
        acceptable=get("quality_ok"),
        # Left null on purpose: the pipeline provides no quality score, and
        # deriving one from the gates below would be a fabricated percentage.
        score=None,
        metrics=FaceQualityMetrics(
            face_width_px=get("face_width"),
            face_height_px=get("face_height"),
            brightness=get("brightness"),
            blur_score=get("blur_score"),
            yaw_proxy=get("yaw_proxy"),
            roll_deg=get("roll"),
        ),
        checks=FaceQualityChecks(
            face_size_ok=get("face_size_ok"),
            brightness_ok=get("brightness_ok"),
            blur_ok=get("blur_ok"),
            pose_ok=get("pose_ok"),
        ),
    )


def from_verification_result(
    case_id: str,
    result: Any,
    *,
    thresholds: Optional[Thresholds] = None,
    model_version: str = ARCFACE_MODEL_VERSION,
) -> Envelope:
    """
    `result` is a `faceverify.pipeline.VerificationResult` (or anything with
    `similarity`, `decision`, `quality_a`, `quality_b`).
    """
    config = (thresholds or load_thresholds()).face

    similarity = float(getattr(result, "similarity"))
    raw_decision = getattr(result, "decision", None)
    decision_value = getattr(raw_decision, "value", raw_decision)

    # The upstream pipeline classifies with the same boundaries this contract
    # publishes. Re-deriving the decision here would create a second place for
    # the rule to live, so the upstream value is trusted and only defaulted when
    # it is absent.
    decision = FaceDecision(decision_value) if decision_value else FaceDecision(
        config.classify(similarity)
    )

    payload = FaceVerificationResult(
        similarity=similarity,
        decision=decision,
        thresholds=FaceThresholdsPayload(match=config.match, review=config.review),
        quality={
            "document_face": _quality_from(getattr(result, "quality_a", None)),
            "live_face": _quality_from(getattr(result, "quality_b", None)),
        },
        embedding_dim=512,
    )
    return success(
        case_id=case_id,
        module=Module.FACE_VERIFICATION,
        model_version=model_version,
        result=payload.to_dict(),
    )


def from_failure(
    case_id: str,
    code: str,
    message: str,
    *,
    retryable: bool = True,
    model_version: str = ARCFACE_MODEL_VERSION,
) -> Envelope:
    """
    A face comparison that could not run - no face found, one image unreadable,
    the model unavailable. Reported as FAILED so the fusion engine excludes it
    rather than scoring it as a non-match.
    """
    return failed(
        case_id=case_id,
        module=Module.FACE_VERIFICATION,
        model_version=model_version,
        errors=[ModuleError(code=code, message=message, retryable=retryable)],
    )
