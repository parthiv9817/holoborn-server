from pydantic import BaseModel, Field


class FramingResponse(BaseModel):
    framing: str = "bad"
    message: str = ""
    landmarks_detected: int = 0
    subject_center_x: float = 0.0
    subject_center_z: float = 0.0
    processing_time_ms: float = 0.0


class GenerateResponse(BaseModel):
    status: str
    task_id: str
    message: str = ""


class MultiviewResponse(BaseModel):
    status: str = "processing"
    task_id: str
    frames_received: int = 0
    message: str = ""


class TaskStatusResponse(BaseModel):
    status: str = "processing"
    progress: int = 0
    glb_url: str = ""
    message: str = ""


class FrameMetadata(BaseModel):
    index: int
    angle: float = 0.0
