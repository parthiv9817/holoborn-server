import cv2
import numpy as np


def decode_jpeg(data: bytes) -> np.ndarray:
    if not data:
        raise ValueError("empty image bytes")
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("could not decode image bytes (not a valid JPEG/PNG?)")
    return frame
