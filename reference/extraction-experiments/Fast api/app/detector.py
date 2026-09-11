"""
detector.py

Wraps best.onnx (your fine-tuned YOLOv12s document detector) behind a small
class so the FastAPI app can load it once at startup and reuse it for every
request. The preprocessing/postprocessing math is copied unchanged from
your step3_perspective_correction_from_detection(target).py, since that was
already verified against the model's real output shape (1, 5, 8400).
"""
from typing import Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from . import config


Box = Tuple[float, float, float, float, float]  # x1, y1, x2, y2, confidence


def _letterbox(image, new_size=640, color=(114, 114, 114)):
    orig_h, orig_w = image.shape[:2]
    scale = min(new_size / orig_h, new_size / orig_w)
    new_unpadded_w = int(round(orig_w * scale))
    new_unpadded_h = int(round(orig_h * scale))
    resized = cv2.resize(image, (new_unpadded_w, new_unpadded_h), interpolation=cv2.INTER_LINEAR)
    pad_w = new_size - new_unpadded_w
    pad_h = new_size - new_unpadded_h
    pad_left, pad_top = pad_w // 2, pad_h // 2
    pad_right, pad_bottom = pad_w - pad_left, pad_h - pad_top
    padded = cv2.copyMakeBorder(resized, pad_top, pad_bottom, pad_left, pad_right,
                                 cv2.BORDER_CONSTANT, value=color)
    return padded, scale, (pad_left, pad_top)


def _preprocess(image_bgr, input_size):
    padded, scale, (pad_left, pad_top) = _letterbox(image_bgr, input_size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0), scale, (pad_left, pad_top)


def _postprocess(raw_output, scale, pad, orig_w, orig_h, conf_thresh, nms_iou):
    preds = raw_output[0].T
    boxes_cxcywh, scores = preds[:, :4], preds[:, 4]
    keep_mask = scores >= conf_thresh
    boxes_cxcywh, scores = boxes_cxcywh[keep_mask], scores[keep_mask]
    if len(scores) == 0:
        return []
    cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    nms_boxes = np.stack([x1, y1, w, h], axis=1).tolist()
    keep_indices = cv2.dnn.NMSBoxes(nms_boxes, scores.tolist(), conf_thresh, nms_iou)
    if len(keep_indices) == 0:
        return []
    keep_indices = np.array(keep_indices).flatten()
    pad_left, pad_top = pad
    results = []
    for i in keep_indices:
        rx1 = max(0, min((x1[i] - pad_left) / scale, orig_w))
        ry1 = max(0, min((y1[i] - pad_top) / scale, orig_h))
        rx2 = max(0, min((x2[i] - pad_left) / scale, orig_w))
        ry2 = max(0, min((y2[i] - pad_top) / scale, orig_h))
        results.append((rx1, ry1, rx2, ry2, float(scores[i])))
    results.sort(key=lambda r: r[4], reverse=True)
    return results


class DocumentDetector:
    """Loads best.onnx once; call .detect(image_bgr) per request."""

    def __init__(self, onnx_path=None, conf_threshold=None, nms_iou=None, input_size=None):
        self.onnx_path = onnx_path or config.YOLO_ONNX_PATH
        self.conf_threshold = conf_threshold if conf_threshold is not None else config.CONF_THRESHOLD
        self.nms_iou = nms_iou if nms_iou is not None else config.NMS_IOU_THRESHOLD
        self.input_size = input_size or config.DETECTOR_INPUT_SIZE

        self.session = ort.InferenceSession(self.onnx_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def detect(self, image_bgr) -> Optional[Box]:
        """Returns the single highest-confidence detection, or None."""
        orig_h, orig_w = image_bgr.shape[:2]
        input_tensor, scale, pad = _preprocess(image_bgr, self.input_size)
        raw_output = self.session.run(None, {self.input_name: input_tensor})[0]
        detections = _postprocess(raw_output, scale, pad, orig_w, orig_h,
                                   self.conf_threshold, self.nms_iou)
        return detections[0] if detections else None
