"""
Adapters from the existing services onto the canonical contracts.

Each upstream service lives in its own repository and is not modified. The
translation lives here so that a change to an upstream response shape is a
change to one adapter rather than to every consumer.
"""

from . import face_arcface, ocr_extraction, validation_rules

__all__ = ["face_arcface", "ocr_extraction", "validation_rules"]
