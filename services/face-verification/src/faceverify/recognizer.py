"""
Stage 6: ArcFace R50 face embedding inference.

Input:
    112x112 aligned BGR face.

Output:
    L2-normalized 512-dimensional face embedding.

This module performs recognition-model inference only.
It does not perform face detection, quality assessment,
alignment, similarity calculation, or final decision making.
"""

import os

import cv2
import numpy as np
import onnxruntime as ort


DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "models",
    "buffalo_m",
    "w600k_r50.onnx",
)


class ArcFaceRecognizer:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):

        if not os.path.isfile(model_path):
            raise FileNotFoundError(
                f"ArcFace model not found: {model_path}"
            )

        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )

        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()

        if len(inputs) != 1:
            raise RuntimeError(
                f"Expected exactly one ArcFace input, got {len(inputs)}"
            )

        if len(outputs) != 1:
            raise RuntimeError(
                f"Expected exactly one ArcFace output, got {len(outputs)}"
            )

        self.input_name = inputs[0].name
        self.output_name = outputs[0].name

        input_shape = inputs[0].shape

        if input_shape[1:] != [3, 112, 112]:
            raise RuntimeError(
                f"Unexpected ArcFace input shape: {input_shape}"
            )

        output_shape = outputs[0].shape

        if output_shape != [1, 512]:
            raise RuntimeError(
                f"Unexpected ArcFace output shape: {output_shape}"
            )

    @staticmethod
    def _preprocess(aligned_face: np.ndarray) -> np.ndarray:
        """
        Convert aligned BGR 112x112 face into ArcFace input.

        ArcFace preprocessing:
            BGR -> RGB
            uint8 -> float32
            normalize using (pixel - 127.5) / 127.5
            HWC -> CHW
            add batch dimension
        """

        if aligned_face is None or aligned_face.size == 0:
            raise ValueError("Aligned face is empty.")

        if aligned_face.shape != (112, 112, 3):
            raise ValueError(
                f"Expected aligned face shape (112, 112, 3), "
                f"got {aligned_face.shape}"
            )

        rgb = cv2.cvtColor(
            aligned_face,
            cv2.COLOR_BGR2RGB,
        )

        face = rgb.astype(np.float32)

        face = (face - 127.5) / 127.5

        face = np.transpose(
            face,
            (2, 0, 1),
        )

        face = np.expand_dims(
            face,
            axis=0,
        )

        return face

    @staticmethod
    def _l2_normalize(embedding: np.ndarray) -> np.ndarray:
        """
        L2-normalize a face embedding.
        """

        norm = np.linalg.norm(embedding)

        if norm <= 1e-12:
            raise ValueError(
                "Cannot normalize a zero-length embedding."
            )

        return embedding / norm

    def get_embedding(
        self,
        aligned_face: np.ndarray,
    ) -> np.ndarray:
        """
        Generate a normalized 512-dimensional ArcFace embedding.
        """

        input_tensor = self._preprocess(
            aligned_face
        )

        output = self.session.run(
            [self.output_name],
            {
                self.input_name: input_tensor
            },
        )[0]

        embedding = output[0].astype(
            np.float32
        )

        if embedding.shape != (512,):
            raise RuntimeError(
                f"Unexpected embedding shape: "
                f"{embedding.shape}"
            )

        embedding = self._l2_normalize(
            embedding
        )

        return embedding