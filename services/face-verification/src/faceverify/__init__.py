"""
faceverify package
SIH26188 / SSB26188 Face Verification Module.

Pipeline:
Document Portrait -> SCRFD-2.5G-KPS -> Face Quality -> 5-point Alignment
-> 112x112 -> ArcFace R50 -> Embedding -> Cosine Similarity
-> calibrated MATCH / REVIEW / NO MATCH -> LightGBM risk engine input
"""

__version__ = "0.1.0"