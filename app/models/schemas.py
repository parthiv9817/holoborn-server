from pydantic import BaseModel, Field


class BBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class FaceDetection(BaseModel):
    bbox: BBox
    confidence: float


class DetectionResponse(BaseModel):
    detected: bool
    face_count: int
    faces: list[FaceDetection] = Field(default_factory=list)
    frame_number: int = 0
    processing_time_ms: float = 0.0


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""


class HealthResponse(BaseModel):
    status: str = "alive"
    frames_processed: int = 0
    uptime_seconds: float = 0.0
