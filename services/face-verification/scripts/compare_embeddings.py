import os
import sys
import numpy as np


EMBEDDING_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "embeddings",
)


THRESHOLD = 0.225


def load_embedding(filename):

    path = os.path.join(
        EMBEDDING_DIR,
        filename,
    )

    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Embedding not found: {path}"
        )

    embedding = np.load(path)

    print(
        f"Loaded {filename}: "
        f"shape={embedding.shape}, "
        f"dtype={embedding.dtype}, "
        f"norm={np.linalg.norm(embedding):.6f}"
    )

    if embedding.shape != (512,):
        raise ValueError(
            f"Invalid embedding shape: {embedding.shape}"
        )

    return embedding


def cosine_similarity(a, b):

    return np.dot(a, b) / (
        np.linalg.norm(a) *
        np.linalg.norm(b)
    )


def main():

    if len(sys.argv) != 3:
        print(
            'Usage: python scripts\\compare_embeddings.py '
            '"DOCUMENT_EMBEDDING.npy" "LIVE_EMBEDDING.npy"'
        )
        sys.exit(1)

    document_filename = sys.argv[1]
    live_filename = sys.argv[2]

    print()
    print("--- LOADING EMBEDDINGS ---")

    document = load_embedding(
        document_filename
    )

    live = load_embedding(
        live_filename
    )

    print()
    print("--- COSINE SIMILARITY ---")

    score = cosine_similarity(
        document,
        live,
    )

    print(
        f"Document <-> Live: {score:.6f}"
    )

    print()
    print("--- VERIFICATION DECISION ---")

    print(
        f"Threshold: {THRESHOLD:.6f}"
    )

    if score >= THRESHOLD:
        decision = "MATCH"
    else:
        decision = "NO MATCH"

    print(
        f"Decision: {decision}"
    )


if __name__ == "__main__":
    main()