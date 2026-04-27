import time

import cv2
import mediapipe as mp
import numpy as np

from app.models.schemas import BBox, FaceDetection


class FaceDetector:
    def __init__(self, min_confidence: float = 0.5, model_selection: int = 1) -> None:
        self._mp = mp.solutions.face_detection.FaceDetection(
            model_selection=model_selection,
            min_detection_confidence=min_confidence,
        )

    def detect_faces(self, frame: np.ndarray) -> tuple[list[FaceDetection], float]:
        start = time.perf_counter()
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._mp.process(rgb)
        faces: list[FaceDetection] = []
        if result.detections:
            for det in result.detections:
                rel = det.location_data.relative_bounding_box
                x = max(0, int(rel.xmin * w))
                y = max(0, int(rel.ymin * h))
                bw = max(0, int(rel.width * w))
                bh = max(0, int(rel.height * h))
                conf = float(det.score[0]) if det.score else 0.0
                faces.append(
                    FaceDetection(
                        bbox=BBox(x=x, y=y, width=bw, height=bh),
                        confidence=conf,
                    )
                )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return faces, elapsed_ms

    def close(self) -> None:
        self._mp.close()
