"""
Stage 7: Face embedding similarity.

Computes cosine similarity between two
L2-normalized ArcFace embeddings.

This module does NOT make MATCH/REVIEW/NO MATCH
decisions. Threshold calibration is a separate stage.
"""

import numpy as np


def cosine_similarity(
    embedding_a: np.ndarray,
    embedding_b: np.ndarray,
) -> float:
    """
    Compute cosine similarity between two embeddings.
    """

    a = np.asarray(
        embedding_a,
        dtype=np.float32,
    )

    b = np.asarray(
        embedding_b,
        dtype=np.float32,
    )

    if a.shape != (512,):
        raise ValueError(
            f"Expected embedding_a shape (512,), got {a.shape}"
        )

    if b.shape != (512,):
        raise ValueError(
            f"Expected embedding_b shape (512,), got {b.shape}"
        )

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a <= 1e-12:
        raise ValueError(
            "embedding_a has near-zero norm."
        )

    if norm_b <= 1e-12:
        raise ValueError(
            "embedding_b has near-zero norm."
        )

    similarity = np.dot(a, b) / (
        norm_a * norm_b
    )

    return float(similarity)