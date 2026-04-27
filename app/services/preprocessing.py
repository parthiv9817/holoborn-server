import numpy as np

from app.services.frame_decoder import decode_jpeg


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
