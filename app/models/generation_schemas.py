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
    """Status response for /generate/{task_id}/status.

    `status` values, in pipeline order:
      "processing"     legacy alias, kept for backwards compat
      "portraitizing"  OpenAI gpt-image-1.5 portrait edit in flight
      "generating"     RunPod TRELLIS generation in flight (progress 0-100)
      "retexturing"    Meshy v6 Retexture (de-lighting + clean PBR) in flight
      "rigging"        Meshy auto-rig in flight (when wired)
      "animating"      Meshy animation bake in flight (when wired)
      "complete"       GLB ready at glb_url (clean Meshy-retextured version)
      "failed"         pipeline failure, see message

    Quest's SpawnRitualController maps these to ritual phases:
      portraitizing / generating / retexturing -> ShellManifest (mannequin holds)
      complete -> Revealed (scan-line transition fires, clean avatar emerges)
      (awakening kicks off after rigging completes — Phase E of UI plan)
    """

    status: str = "processing"
    progress: int = 0
    glb_url: str = ""
    message: str = ""


class FrameMetadata(BaseModel):
    index: int
    angle: float = 0.0
