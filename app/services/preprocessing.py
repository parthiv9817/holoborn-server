import cv2
import numpy as np

from app.services.frame_decoder import decode_jpeg


def pick_sharpest(jpeg_frames: list[bytes]) -> tuple[bytes, int, float]:
    """Pick the sharpest JPEG from a burst by variance-of-Laplacian.

    Higher variance = more high-frequency content = less motion blur. The metric
    is computed on a grayscale downscale (480px-wide) for speed; the returned
    bytes are the original full-resolution JPEG.

    Returns (jpeg_bytes, index, score). Raises ValueError on empty input.
    """
    if not jpeg_frames:
        raise ValueError("pick_sharpest requires at least one frame")

    if len(jpeg_frames) == 1:
        bgr = decode_jpeg(jpeg_frames[0])
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()
        return jpeg_frames[0], 0, float(score)

    best_idx = 0
    best_score = -1.0
    for i, raw in enumerate(jpeg_frames):
        bgr = decode_jpeg(raw)
        h, w = bgr.shape[:2]
        if w > 480:
            scale = 480.0 / w
            bgr = cv2.resize(bgr, (480, int(h * scale)), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if score > best_score:
            best_score = score
            best_idx = i
    return jpeg_frames[best_idx], best_idx, best_score


def burst_average(jpeg_frames: list[bytes]) -> np.ndarray:
    if not jpeg_frames:
        raise ValueError("burst_average requires at least one frame")

    if len(jpeg_frames) == 1:
        return decode_jpeg(jpeg_frames[0])

    decoded = [decode_jpeg(b) for b in jpeg_frames]
    h, w = decoded[0].shape[:2]
    for i, frame in enumerate(decoded[1:], start=1):
        if frame.shape[:2] != (h, w):
            raise ValueError(
                f"frame {i} shape {frame.shape[:2]} doesn't match frame 0 shape {(h, w)}"
            )

    stack = np.stack([f.astype(np.float32) for f in decoded], axis=0)
    averaged = stack.mean(axis=0)
    return np.clip(averaged, 0, 255).astype(np.uint8)
