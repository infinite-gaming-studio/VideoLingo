"""
Shared Pydantic Models for VideoLingo Cloud API
Used by both client and server
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from videolingo_cloud._version import SERVER_VERSION


class TranscriptionRequest(BaseModel):
    """Request model for ASR transcription"""
    language: Optional[str] = Field(default=None, description="Language code (e.g., 'en', 'zh')")
    model: str = Field(default="large-v3", description="Whisper model")
    batch_size: Optional[int] = Field(default=None, description="Batch size")
    vad_onset: float = Field(default=0.500, description="VAD onset threshold")
    vad_offset: float = Field(default=0.363, description="VAD offset threshold")
    align: bool = Field(default=True, description="Perform word-level alignment")
    speaker_diarization: bool = Field(default=False, description="Perform speaker diarization")
    min_speakers: Optional[int] = Field(default=None, description="Minimum number of speakers")
    max_speakers: Optional[int] = Field(default=None, description="Maximum number of speakers")


class TranscriptionResponse(BaseModel):
    """Response model for ASR transcription"""
    success: bool
    language: str
    segments: list
    word_segments: Optional[list] = None
    speakers: Optional[list] = None
    processing_time: float
    device: str
    model: str
    server_version: str = SERVER_VERSION


class SeparationResponse(BaseModel):
    """Response model for audio separation"""
    success: bool
    vocals_base64: Optional[str] = None
    background_base64: Optional[str] = None
    processing_time: float
    device: str
    server_version: str = SERVER_VERSION


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    device: str
    cuda_available: bool
    mps_available: bool
    gpu_memory: Optional[float] = None
    whisper_models_loaded: list
    demucs_model_loaded: bool
    align_models_loaded: list
    diarize_model_loaded: bool
    services: dict
    server_version: str = SERVER_VERSION
    platform: str


class ServiceInfo(BaseModel):
    """Service availability info"""
    available: bool
    endpoint: str
