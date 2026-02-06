"""
WhisperX Cloud API Server
Deploy whisperX as a standalone service on GPU cloud platforms (Colab, Kaggle, etc.)
Compatible with VideoLingo project
"""

# Server version
SERVER_VERSION = "1.3.0"

import os
import builtins
# Set matplotlib backend to Agg before importing any matplotlib-dependent libraries
os.environ['MPLBACKEND'] = 'Agg'

# Monkey patch builtins.open to ensure all file operations use the same settings
_original_open = open
def _patched_open(*args, **kwargs):
    return _original_open(*args, **kwargs)
builtins.open = _patched_open

import io
import base64
import tempfile
import warnings
import time
from typing import Optional
from contextlib import asynccontextmanager

import torch

# Patch torch.load to disable weights_only restriction for PyTorch 2.6+
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    # Always set weights_only=False to allow loading legacy models
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
# Replace torch.load in the torch module
torch.load = _patched_torch_load

# Also patch in builtins to catch any direct imports
import sys
sys.modules['torch'].load = _patched_torch_load

import whisperx
import librosa
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# ============== Logging ==============
try:
    from rich.console import Console
    _console = Console(log_time=True)
    def vvprint(*args, **kwargs):
        _console.log(*args, **kwargs)
except ImportError:
    import datetime
    def vvprint(*args, **kwargs):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vprint(f"[{timestamp}]", *args, **kwargs)

warnings.filterwarnings("ignore")

# Security
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify the bearer token against environment variable"""
    token = os.getenv("VIDEOLINGO_CLOUD_TOKEN") or os.getenv("WHISPER_SERVER_TOKEN") or os.getenv("WHISPERX_CLOUD_TOKEN")
    if not token:
        # If no token is set in environment, allow all requests (or warn?)
        # For security, let's say if variable is not set, we assume no auth needed? 
        # Or better: check if it matches. 
        # If WHISPER_SERVER_TOKEN is not set, we skip auth.
        return True
    
    if credentials.credentials != token:
        raise HTTPException(status_code=403, detail="Invalid authentication token")
    return True

# Global model cache
model_cache = {}
align_model_cache = {}
diarize_model_cache = {}
device = None
compute_type = None

def get_device():
    """智能设备检测: CUDA -> MPS (Apple Silicon) -> CPU"""
    if torch.cuda.is_available():
        return "cuda", "float16" if torch.cuda.is_bf16_supported() else "int8"
    elif torch.backends.mps.is_available():
        return "mps", "float16"
    else:
        return "cpu", "int8"

class TranscriptionRequest(BaseModel):
    language: Optional[str] = Field(default=None, description="Language code (e.g., 'en', 'zh', 'ja'). Auto-detect if not provided")
    model: str = Field(default="large-v3", description="Whisper model to use")
    batch_size: Optional[int] = Field(default=None, description="Batch size for transcription")
    vad_onset: float = Field(default=0.500, description="VAD onset threshold")
    vad_offset: float = Field(default=0.363, description="VAD offset threshold")
    align: bool = Field(default=True, description="Perform word-level alignment")
    speaker_diarization: bool = Field(default=False, description="Perform speaker diarization")
    min_speakers: Optional[int] = Field(default=None, description="Minimum number of speakers")
    max_speakers: Optional[int] = Field(default=None, description="Maximum number of speakers")

class TranscriptionResponse(BaseModel):
    success: bool
    language: str
    segments: list
    word_segments: Optional[list] = None
    speakers: Optional[list] = None
    processing_time: float
    device: str
    model: str
    server_version: str = SERVER_VERSION

class HealthResponse(BaseModel):
    status: str
    device: str
    cuda_available: bool
    mps_available: bool
    gpu_memory: Optional[float] = None
    models_loaded: list
    align_models_loaded: list
    diarize_model_loaded: bool
    server_version: str = SERVER_VERSION
    platform: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup, cleanup on shutdown"""
    global device, compute_type

    # Print server version on startup
    vprint(f"📌 WhisperX Cloud Server v{SERVER_VERSION}")
    vprint(f"   With PyTorch weights_only patch for PyTorch 2.6+ compatibility\n")

    # Preload models
    vprint("📦 Preloading models...")
    get_or_load_model("large-v3")
    
    try:
        get_or_load_align_model("en")
        get_or_load_align_model("zh")
    except Exception as e:
        vprint(f"⚠️ Failed to preload some alignment models: {e}")
        
    try:
        get_or_load_diarize_model()
    except Exception as e:
        vprint(f"⚠️ Failed to preload diarization model: {e}")
        
    vprint("✅ All models loaded!\n")

    yield

    # Cleanup
    vprint("Cleaning up models...")
    model_cache.clear()
    align_model_cache.clear()
    diarize_model_cache.clear()
    if device == "cuda":
        torch.cuda.empty_cache()

app = FastAPI(
    title="WhisperX Cloud API",
    description="Standalone WhisperX ASR service for VideoLingo",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_or_load_model(model_name: str, language: Optional[str] = None, batch_size: int = 16):
    """Load or retrieve cached model"""
    cache_key = f"{model_name}_{language}_{compute_type}"
    
    if cache_key not in model_cache:
        vprint(f"📥 Loading model: {model_name}...")
        vad_options = {"vad_onset": 0.500, "vad_offset": 0.363}
        asr_options = {"temperatures": [0], "initial_prompt": ""}
        
        model = whisperx.load_model(
            model_name,
            device,
            compute_type=compute_type,
            language=language,
            vad_options=vad_options,
            asr_options=asr_options
        )
        model_cache[cache_key] = model
        vprint(f"✅ Model loaded: {model_name}")
    
    return model_cache[cache_key]

def get_or_load_align_model(language_code: str):
    """Load or retrieve cached alignment model"""
    if language_code not in align_model_cache:
        vprint(f"📥 Loading alignment model for: {language_code}...")
        align_model, align_metadata = whisperx.load_align_model(
            language_code=language_code, device=device
        )
        align_model_cache[language_code] = (align_model, align_metadata)
        vprint(f"✅ Alignment model loaded: {language_code}")
    return align_model_cache[language_code]

def get_or_load_diarize_model():
    """Load or retrieve cached diarization model"""
    if 'diarize' not in diarize_model_cache:
        vprint(f"📥 Loading Diarization model on {device}...")
        diarize_model = whisperx.DiarizationPipeline(
            model_name="pyannote/speaker-diarization-3.1", device=device
        )
        diarize_model_cache['diarize'] = diarize_model
        vprint(f"✅ Diarization model loaded")
    return diarize_model_cache['diarize']

def process_audio(audio_bytes: bytes):
    """Load and preprocess audio"""
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    
    try:
        # Load audio at 16kHz
        audio, sr = librosa.load(tmp_path, sr=16000, mono=True)
        return audio
    finally:
        os.unlink(tmp_path)

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    gpu_mem = None
    cuda_avail = torch.cuda.is_available()
    mps_avail = torch.backends.mps.is_available()
    
    if cuda_avail:
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        platform_str = "cuda"
    elif mps_avail:
        platform_str = "mps"
    else:
        platform_str = "cpu"
    
    return HealthResponse(
        status="healthy",
        device=device,
        cuda_available=cuda_avail,
        mps_available=mps_avail,
        gpu_memory=gpu_mem,
        models_loaded=list(model_cache.keys()),
        align_models_loaded=list(align_model_cache.keys()),
        diarize_model_loaded='diarize' in diarize_model_cache,
        platform=platform_str
    )

@app.post("/transcribe", response_model=TranscriptionResponse, dependencies=[Depends(verify_token)])
async def transcribe(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, m4a, etc.)"),
    language: Optional[str] = None,
    model: str = "large-v3",
    batch_size: Optional[int] = None,
    vad_onset: float = 0.500,
    vad_offset: float = 0.363,
    align: bool = True,
    speaker_diarization: bool = False,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
):
    """
    Transcribe audio file using WhisperX
    
    Returns word-level timestamps compatible with VideoLingo format
    """
    start_time = time.time()
    
    # Determine batch size based on device
    if batch_size is None:
        if device == "cuda":
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            batch_size = 16 if gpu_mem > 8 else 4
        elif device == "mps":
            batch_size = 4  # MPS建议使用较小的batch_size
        else:
            batch_size = 1  # CPU模式使用最小batch_size
    
    try:
        # Read audio file
        audio_bytes = await audio.read()
        audio_array = process_audio(audio_bytes)
        
        # Load model
        whisper_model = get_or_load_model(model, language, batch_size)
        
        # Transcribe
        vprint("🎯 Starting transcription...")
        result = whisper_model.transcribe(audio_array, batch_size=batch_size)
        detected_language = result.get("language", language or "unknown")
        segments = result.get("segments", [])
        
        # Word-level alignment
        word_segments = None
        if align and segments:
            vprint("🔄 Aligning words...")
            align_model, align_metadata = get_or_load_align_model(detected_language)
            result_aligned = whisperx.align(
                segments,
                align_model,
                align_metadata,
                audio_array,
                device,
                return_char_alignments=False
            )
            segments = result_aligned.get("segments", [])
            word_segments = result_aligned.get("word_segments", [])
        
        # Speaker diarization
        speakers = None
        if speaker_diarization:
            vprint("🎭 Performing speaker diarization...")
            diarize_model = get_or_load_diarize_model()
            diarize_segments = diarize_model(audio_array, min_speakers=min_speakers, max_speakers=max_speakers)
            result_diarized = whisperx.assign_word_speakers(diarize_segments, {"segments": segments})
            segments = result_diarized.get("segments", [])
            speakers = list(set(seg.get("speaker", "UNKNOWN") for seg in segments if "speaker" in seg))
        
        processing_time = time.time() - start_time

        return TranscriptionResponse(
            success=True,
            language=detected_language,
            segments=segments,
            word_segments=word_segments,
            speakers=speakers,
            processing_time=processing_time,
            device=device,
            model=model,
            server_version=SERVER_VERSION
        )
        
    except Exception as e:
        vprint(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if device == "cuda":
            torch.cuda.empty_cache()

@app.post("/transcribe/base64")
async def transcribe_base64(request: TranscriptionRequest):
    """
    Transcribe base64-encoded audio (for smaller files)
    
    Note: This endpoint expects a JSON body with base64 audio data
    Use /transcribe for file uploads instead
    """
    # This is a placeholder for base64 transcription
    # In practice, you'd implement similar logic with base64 decoding
    raise HTTPException(status_code=501, detail="Base64 endpoint not implemented yet")

@app.delete("/cache", dependencies=[Depends(verify_token)])
async def clear_cache():
    """Clear model cache to free GPU memory"""
    global model_cache, align_model_cache, diarize_model_cache
    model_cache.clear()
    align_model_cache.clear()
    diarize_model_cache.clear()
    if device == "cuda":
        torch.cuda.empty_cache()
    return {"status": "Cache cleared"}

if __name__ == "__main__":
    # For local testing
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
