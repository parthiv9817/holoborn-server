import time

import cv2
import mediapipe as mp
import numpy as np


KNEE_LEFT, KNEE_RIGHT = 25, 26
ANKLE_LEFT, ANKLE_RIGHT = 27, 28
HIP_LEFT, HIP_RIGHT = 23, 24
SHOULDER_LEFT, SHOULDER_RIGHT = 11, 12
VISIBILITY_THRESHOLD = 0.5


class PoseValidator:
    def __init__(self, min_detection_confidence: float = 0.5) -> None:
        self._mp = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
        )

    def validate_framing(self, frame: np.ndarray) -> dict:
        start = time.perf_counter()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._mp.process(rgb)

        framing = "bad"
        message = ""
        landmarks_detected = 0
        center_x = 0.0
        center_z = 0.0

        if not result.pose_landmarks:
            message = "no person detected"
        else:
            landmarks = result.pose_landmarks.landmark
            landmarks_detected = sum(1 for lm in landmarks if lm.visibility > VISIBILITY_THRESHOLD)

            knees_visible = (
                landmarks[KNEE_LEFT].visibility > VISIBILITY_THRESHOLD
                and landmarks[KNEE_RIGHT].visibility > VISIBILITY_THRESHOLD
            )
            ankles_visible = (
                landmarks[ANKLE_LEFT].visibility > VISIBILITY_THRESHOLD
                and landmarks[ANKLE_RIGHT].visibility > VISIBILITY_THRESHOLD
            )

            if knees_visible and ankles_visible:
                framing = "good"
                message = "full body visible"
            elif not knees_visible:
                message = "knees not visible — step back"
            else:
                message = "ankles not visible — step back"

            hip_l = landmarks[HIP_LEFT]
            hip_r = landmarks[HIP_RIGHT]
            center_x = float((hip_l.x + hip_r.x) / 2.0)
            center_z = float((hip_l.z + hip_r.z) / 2.0)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "framing": framing,
            "message": message,
            "landmarks_detected": landmarks_detected,
            "subject_center_x": center_x,
            "subject_center_z": center_z,
            "processing_time_ms": elapsed_ms,
        }

    def close(self) -> None:
        self._mp.close()
