"""
Stage 3: Standalone SCRFD-2.5G-KPS face detector.
No InsightFace package dependency - explicit ONNX Runtime inference.
"""
import os
from dataclasses import dataclass, field
from typing import List

import cv2
import numpy as np
import onnxruntime as ort

# Detection confidence threshold.
# NOTE: this is a DETECTION threshold (is this a face?), NOT a
# biometric verification/match threshold. Do not reuse this value
# for MATCH/REVIEW/NO MATCH decisions in later stages.
DEFAULT_DET_THRESHOLD = 0.5
DEFAULT_NMS_THRESHOLD = 0.4
DEFAULT_INPUT_SIZE = (640, 640)  # (width, height) fed to the network


class ImageLoadError(Exception):
    pass


@dataclass
class DetectedFace:
    bbox: List[float]              # [x1, y1, x2, y2]
    confidence: float
    left_eye: List[float]
    right_eye: List[float]
    nose: List[float]
    left_mouth: List[float]
    right_mouth: List[float]


def _distance2bbox(points, distance):
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points, distance):
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def _nms(dets: np.ndarray, thresh: float) -> List[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]
    return keep


class SCRFDDetector:
    def __init__(self, model_path: str):
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"SCRFD model not found: {model_path}")
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        if len(self.output_names) != 9:
            raise RuntimeError(
                f"Expected 9 SCRFD outputs (3 strides x score/bbox/kps), got {len(self.output_names)}"
            )
        self.fmc = 3
        self.strides = [8, 16, 32]
        self.num_anchors = 2
        self.input_mean = 127.5
        self.input_std = 128.0
        self.center_cache = {}

    def _preprocess(self, img, input_size):
        iw, ih = input_size
        h, w = img.shape[:2]
        scale = min(iw / w, ih / h)
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(img, (new_w, new_h))
        padded = np.zeros((ih, iw, 3), dtype=np.uint8)
        padded[:new_h, :new_w, :] = resized
        blob = cv2.dnn.blobFromImage(
            padded, 1.0 / self.input_std, (iw, ih),
            (self.input_mean, self.input_mean, self.input_mean), swapRB=True
        )
        return blob, scale

    def _get_anchor_centers(self, height, width, stride):
        key = (height, width, stride)
        if key in self.center_cache:
            return self.center_cache[key]
        centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
        centers = (centers * stride).reshape((-1, 2))
        centers = np.stack([centers] * self.num_anchors, axis=1).reshape((-1, 2))
        if len(self.center_cache) < 100:
            self.center_cache[key] = centers
        return centers

    def detect(self, image_path: str, det_threshold: float = DEFAULT_DET_THRESHOLD,
               nms_threshold: float = DEFAULT_NMS_THRESHOLD,
               input_size=DEFAULT_INPUT_SIZE) -> List[DetectedFace]:
        img = cv2.imread(image_path)
        if img is None:
            raise ImageLoadError(f"Could not load image (bad path or unsupported format): {image_path}")

        blob, scale = self._preprocess(img, input_size)
        outs = self.session.run(self.output_names, {self.input_name: blob})

        iw, ih = input_size
        scores_all, bboxes_all, kpss_all = [], [], []

        for idx, stride in enumerate(self.strides):
            scores = outs[idx].reshape(-1)
            bbox_preds = outs[idx + self.fmc].reshape(-1, 4) * stride
            kps_preds = outs[idx + self.fmc * 2].reshape(-1, 10) * stride

            height, width = ih // stride, iw // stride
            centers = self._get_anchor_centers(height, width, stride)

            pos = np.where(scores >= det_threshold)[0]
            if pos.size == 0:
                continue
            bboxes = _distance2bbox(centers, bbox_preds)[pos] / scale
            kpss = _distance2kps(centers, kps_preds)[pos] / scale
            kpss = kpss.reshape(-1, 5, 2)

            scores_all.append(scores[pos])
            bboxes_all.append(bboxes)
            kpss_all.append(kpss)

        if not scores_all:
            return []

        scores_all = np.concatenate(scores_all)
        bboxes_all = np.concatenate(bboxes_all)
        kpss_all = np.concatenate(kpss_all)

        dets = np.hstack([bboxes_all, scores_all[:, None]])
        keep = _nms(dets, nms_threshold)

        faces = []
        for i in keep:
            bbox = bboxes_all[i].tolist()
            kps = kpss_all[i]
            faces.append(DetectedFace(
                bbox=bbox,
                confidence=float(scores_all[i]),
                left_eye=kps[0].tolist(),
                right_eye=kps[1].tolist(),
                nose=kps[2].tolist(),
                left_mouth=kps[3].tolist(),
                right_mouth=kps[4].tolist(),
            ))
        return faces


def get_capture_status(num_faces: int) -> str:
    if num_faces == 0:
        return "RECAPTURE"
    if num_faces == 1:
        return "ACCEPT_FOR_NEXT_STAGE"
    return "INVALID_CAPTURE"