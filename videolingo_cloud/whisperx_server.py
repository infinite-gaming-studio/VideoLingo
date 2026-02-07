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
from typing import Optional, Union, Any
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
    def vprint(*args, **kwargs):
        _console.log(*args, **kwargs)
except ImportError:
    import datetime
    def vprint(*args, **kwargs):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}]", *args, **kwargs, flush=True)

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

# Helper function to parse boolean from form data
def parse_bool(value: Any) -> bool:
    """Parse boolean value from form data (string or bool)"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)

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
    hf_token: Optional[str] = Field(default=None, description="Hugging Face access token for diarization model")

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

    device, compute_type = get_device()
    vprint(f"🚀 Using device: {device} ({compute_type})")

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

        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")

        vprint(f"   🔑 HF_TOKEN present: {'Yes' if hf_token else 'No (WARNING: token required for diarization)'}")
        if hf_token:
            vprint(f"   🔑 Token prefix: {hf_token[:10]}...")

        try:
            vprint(f"   ⏳ Loading pyannote/speaker-diarization-3.1...")
            diarize_model = whisperx.diarize.DiarizationPipeline(
                model_name="pyannote/speaker-diarization-3.1",
                device=device,
                use_auth_token=hf_token
            )
            diarize_model_cache['diarize'] = diarize_model
            vprint(f"   ✅ Diarization model loaded successfully")
        except AttributeError as e:
            if "NoneType" in str(e) and "to" in str(e):
                 vprint(f"   ❌ Failed to load: HF_TOKEN invalid or missing")
                 raise ValueError("Failed to load pyannote pipeline. Please check your HF_TOKEN and model permissions.") from e
            raise e
        except Exception as e:
            vprint(f"   ❌ Failed to load diarization model: {str(e)}")
            raise e
    else:
        vprint(f"   ♻️ Using cached diarization model")
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
    align: Union[bool, str] = True,
    speaker_diarization: Union[bool, str] = False,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None
):
    """
    Transcribe audio file using WhisperX

    Returns word-level timestamps compatible with VideoLingo format
    """
    start_time = time.time()
    
    # Parse boolean parameters from form data
    align = parse_bool(align)
    speaker_diarization = parse_bool(speaker_diarization)
    
    # 📝 Print input parameters
    vprint("=" * 60)
    vprint("📥 NEW TRANSCRIBE REQUEST")
    vprint("=" * 60)
    vprint(f"   🎵 Audio file: {audio.filename}")
    vprint(f"   🌐 Language: {language or 'auto-detect'}")
    vprint(f"   🤖 Model: {model}")
    vprint(f"   🎯 Align: {align}")
    vprint(f"   🎭 Speaker Diarization: {speaker_diarization}")
    if speaker_diarization:
        vprint(f"   👥 Min speakers: {min_speakers}, Max speakers: {max_speakers}")
    vprint("-" * 60)
    # Determine batch size based on device
    if batch_size is None:
        if device == "cuda":
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            batch_size = 16 if gpu_mem > 8 else 4
        elif device == "mps":
            batch_size = 4  # MPS建议使用较小的batch_size
        else:
            batch_size = 1  # CPU模式使用最小batch_size
    vprint(f"   ⚙️ Batch size: {batch_size}")

    try:
        # Read audio file
        audio_bytes = await audio.read()
        vprint(f"   📦 Audio size: {len(audio_bytes) / 1024 / 1024:.2f} MB")

        audio_array = process_audio(audio_bytes)
        vprint(f"   🎚️ Audio duration: {len(audio_array) / 16000:.2f} seconds")

        # Load model
        whisper_model = get_or_load_model(model, language, batch_size)

        # Transcribe
        vprint("🎯 Starting transcription...")
        result = whisper_model.transcribe(audio_array, batch_size=batch_size)
        detected_language = result.get("language", language or "unknown")
        segments = result.get("segments", [])
        vprint(f"   ✅ Transcription complete: {len(segments)} segments")
        vprint(f"   🌍 Detected language: {detected_language}")
        
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
            vprint(f"   ✅ Alignment complete: {len(word_segments)} word segments")

        # Speaker diarization
        speakers = None
        if speaker_diarization:
            vprint("🎭 Performing speaker diarization...")
<<<<<<< HEAD
            try:
                diarize_model = get_or_load_diarize_model()
                diarize_segments = diarize_model(audio_array, min_speakers=min_speakers, max_speakers=max_speakers)
            diarize_model = get_or_load_diarize_model()
            diarize_segments = diarize_model(audio_array, min_speakers=min_speakers, max_speakers=max_speakers)
            
            vprint(f"   ✅ Diarization complete: {len(diarize_segments)} speaker segments")
            vprint(f"   📊 Sample diarize segments (first 3):")
            for i, seg in enumerate(diarize_segments[:3]):
                vprint(f"      [{i}] {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s | Speaker: {seg.get('speaker', 'N/A')}")
            
            # Create result dict with word segments for speaker assignment
            result_for_diarization = {"segments": segments}
            if word_segments:
                result_for_diarization["word_segments"] = word_segments
            
            vprint("   🔗 Assigning speakers to word segments...")
            result_diarized = whisperx.assign_word_speakers(diarize_segments, result_for_diarization)
            segments = result_diarized.get("segments", [])

            # Debug: Check first few segments for speaker
            vprint("   📋 Sample segments after assignment (first 5):")
            for i, seg in enumerate(segments[:5]):
                speaker = seg.get('speaker', 'NOT_SET')
                text_preview = seg.get('text', '')[:30] + '...' if len(seg.get('text', '')) > 30 else seg.get('text', '')
                vprint(f"      [{i}] {seg.get('start', 0):.2f}s - {seg.get('end', 0):.2f}s | Speaker: {speaker} | Text: {text_preview}")

            speakers = list(set(seg.get("speaker", "UNKNOWN") for seg in segments if "speaker" in seg and seg.get("speaker")))
            vprint(f"   👥 Unique speakers found: {speakers}")
        
>>>>>>> main
        processing_time = time.time() - start_time

        # 📝 Print response summary
        vprint("-" * 60)
        vprint("📤 RESPONSE SUMMARY")
        vprint("-" * 60)
        vprint(f"   ✅ Success: True")
        vprint(f"   🌍 Language: {detected_language}")
        vprint(f"   📊 Total segments: {len(segments)}")
        vprint(f"   🔤 Word segments: {len(word_segments) if word_segments else 0}")
        vprint(f"   👥 Speakers: {speakers if speakers else 'N/A (diarization disabled)'}")
        vprint(f"   ⏱️ Processing time: {processing_time:.2f}s")
        vprint("=" * 60)

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
        import traceback
        vprint(f"📄 Traceback: {traceback.format_exc()}")
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
