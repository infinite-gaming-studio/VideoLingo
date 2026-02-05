"""
VideoLingo Unified Cloud API Server
Combines WhisperX (ASR) and Demucs (Vocal Separation) services

Endpoints:
- /health          - Health check for all services
- /asr/*           - WhisperX ASR endpoints
- /separation/*    - Demucs vocal separation endpoints

Deploy on GPU cloud platforms (Colab, Kaggle, etc.)
"""

SERVER_VERSION = "2.1.0"

import os
import sys
import builtins

# Set matplotlib backend to Agg before importing any matplotlib-dependent libraries
os.environ['MPLBACKEND'] = 'Agg'

# Monkey patch builtins.open
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

# Patch torch.load for PyTorch 2.6+ compatibility
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
import sys
sys.modules['torch'].load = _patched_torch_load

import whisperx
import librosa
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Demucs imports
try:
    from demucs.pretrained import get_model
    from demucs.audio import save_audio
    from demucs.apply import apply_model
    from demucs.hdemucs import HDemucs
    DEMUC_AVAILABLE = True
except ImportError:
    DEMUC_AVAILABLE = False
    print("⚠️ Demucs not available, separation service disabled")

import gc

warnings.filterwarnings("ignore")

# Global caches
whisper_model_cache = {}
demucs_model_cache = {}
device = None
compute_type = None

def get_device():
    """Smart device detection: CUDA -> MPS -> CPU"""
    if torch.cuda.is_available():
        return "cuda", "float16" if torch.cuda.is_bf16_supported() else "int8"
    elif torch.backends.mps.is_available():
        return "mps", "float16"
    else:
        return "cpu", "int8"

# ============== Pydantic Models ==============

class TranscriptionRequest(BaseModel):
    language: Optional[str] = Field(default=None, description="Language code (e.g., 'en', 'zh')")
    model: str = Field(default="large-v3", description="Whisper model")
    batch_size: Optional[int] = Field(default=None, description="Batch size")
    vad_onset: float = Field(default=0.500)
    vad_offset: float = Field(default=0.363)
    align: bool = Field(default=True)
    speaker_diarization: bool = Field(default=False)
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

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

class SeparationResponse(BaseModel):
    success: bool
    vocals_base64: Optional[str] = None
    background_base64: Optional[str] = None
    processing_time: float
    device: str
    server_version: str = SERVER_VERSION

class HealthResponse(BaseModel):
    status: str
    device: str
    cuda_available: bool
    mps_available: bool
    gpu_memory: Optional[float] = None
    whisper_models_loaded: list
    demucs_model_loaded: bool
    services: dict
    server_version: str = SERVER_VERSION
    platform: str

# ============== Model Loading ==============

def get_or_load_whisper_model(model_name: str, language: Optional[str] = None, batch_size: int = 16):
    """Load or retrieve cached Whisper model"""
    cache_key = f"{model_name}_{language}_{compute_type}"
    
    if cache_key not in whisper_model_cache:
        print(f"📥 Loading Whisper model: {model_name}...")
        vad_options = {"vad_onset": 0.500, "vad_offset": 0.363}
        asr_options = {"temperatures": [0], "initial_prompt": ""}
        
        model = whisperx.load_model(
            model_name, device, compute_type=compute_type,
            language=language, vad_options=vad_options, asr_options=asr_options
        )
        whisper_model_cache[cache_key] = model
        print(f"✅ Whisper model loaded: {model_name}")
    
    return whisper_model_cache[cache_key]

def get_or_load_demucs_model():
    """Load or retrieve cached Demucs model"""
    if not DEMUC_AVAILABLE:
        return None

    if 'htdemucs' not in demucs_model_cache:
        print("📥 Loading Demucs model...")
        model = get_model('htdemucs')
        model.eval()
        model.to(device)
        demucs_model_cache['htdemucs'] = model
        print("✅ Demucs model loaded")

    return demucs_model_cache['htdemucs']

# ============== Audio Processing ==============

def process_audio(audio_bytes: bytes):
    """Load and preprocess audio"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    
    try:
        audio, sr = librosa.load(tmp_path, sr=16000, mono=True)
        return audio
    finally:
        os.unlink(tmp_path)

# ============== Lifespan ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup"""
    global device, compute_type
    
    print(f"📌 VideoLingo Unified Cloud Server v{SERVER_VERSION}\n")
    
    device, compute_type = get_device()
    
    if device == "cuda":
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"🚀 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        print(f"💾 GPU Memory: {gpu_mem:.2f} GB")
    elif device == "mps":
        print(f"🍎 Using Apple Silicon MPS")
    else:
        print("💻 Using CPU")
    print(f"⚙️ Compute type: {compute_type}\n")
    
    # Preload models
    print("📦 Preloading models...")
    get_or_load_whisper_model("large-v3")
    if DEMUC_AVAILABLE:
        get_or_load_demucs_model()
    print("✅ All models loaded!\n")
    
    yield
    
    # Cleanup
    print("Cleaning up...")
    whisper_model_cache.clear()
    demucs_model_cache.clear()
    if device == "cuda":
        torch.cuda.empty_cache()

# ============== FastAPI App ==============

app = FastAPI(
    title="VideoLingo Unified Cloud API",
    description="Combined WhisperX ASR and Demucs Vocal Separation",
    version=SERVER_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Routers ==============

# ASR Router
asr_router = APIRouter(prefix="/asr", tags=["ASR - WhisperX"])

@asr_router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: Optional[str] = None,
    model: str = "large-v3",
    batch_size: Optional[int] = None,
    align: bool = True,
    speaker_diarization: bool = False
):
    """Transcribe audio using WhisperX"""
    start_time = time.time()
    
    if batch_size is None:
        if device == "cuda":
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            batch_size = 16 if gpu_mem > 8 else 4
        elif device == "mps":
            batch_size = 4
        else:
            batch_size = 1
    
    try:
        audio_bytes = await audio.read()
        audio_array = process_audio(audio_bytes)
        
        whisper_model = get_or_load_whisper_model(model, language, batch_size)
        
        print("🎯 Transcribing...")
        result = whisper_model.transcribe(audio_array, batch_size=batch_size)
        detected_language = result.get("language", language or "unknown")
        segments = result.get("segments", [])
        
        # Word alignment
        word_segments = None
        if align and segments:
            print("🔄 Aligning words...")
            align_model, align_metadata = whisperx.load_align_model(
                language_code=detected_language, device=device
            )
            result_aligned = whisperx.align(
                segments, align_model, align_metadata, audio_array, device,
                return_char_alignments=False
            )
            segments = result_aligned.get("segments", [])
            word_segments = result_aligned.get("word_segments", [])
            del align_model
            if device == "cuda":
                torch.cuda.empty_cache()
        
        # Speaker diarization
        speakers = None
        if speaker_diarization:
            print("🎭 Speaker diarization...")
            diarize_model = whisperx.DiarizationPipeline(
                model_name="pyannote/speaker-diarization-3.1", device=device
            )
            diarize_segments = diarize_model(audio_array)
            result_diarized = whisperx.assign_word_speakers(diarize_segments, {"segments": segments})
            segments = result_diarized.get("segments", [])
            speakers = list(set(seg.get("speaker", "UNKNOWN") for seg in segments if "speaker" in seg))
        
        processing_time = time.time() - start_time
        
        return TranscriptionResponse(
            success=True, language=detected_language, segments=segments,
            word_segments=word_segments, speakers=speakers,
            processing_time=processing_time, device=device, model=model
        )
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if device == "cuda":
            torch.cuda.empty_cache()

# Separation Router
separation_router = APIRouter(prefix="/separation", tags=["Separation - Demucs"])

@separation_router.post("/separate", response_model=SeparationResponse)
async def separate_audio(
    audio: UploadFile = File(...),
    return_files: bool = True
):
    """Separate audio into vocals and background using Demucs"""
    if not DEMUC_AVAILABLE:
        raise HTTPException(status_code=503, detail="Demucs service not available")
    
    start_time = time.time()
    
    try:
        audio_bytes = await audio.read()
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_input:
            tmp_input.write(audio_bytes)
            input_path = tmp_input.name
        
        try:
            model = get_or_load_demucs_model()

            print("🎵 Separating audio...")
            # Load audio file
            from torchaudio import load as torchaudio_load
            from torchaudio import transforms as T
            wav, sr = torchaudio_load(input_path)
            wav = wav.to(device)

            # Ensure stereo (2 channels) for demucs
            if wav.shape[0] == 1:
                print("⚠️ Input is mono, converting to stereo...")
                wav = wav.repeat(2, 1)  # Repeat mono to stereo
            elif wav.shape[0] > 2:
                print("⚠️ Input has more than 2 channels, using first 2...")
                wav = wav[:2, :]

            # Resample to model's expected sample rate if needed
            if sr != model.samplerate:
                print(f"⚠️ Resampling from {sr}Hz to {model.samplerate}Hz...")
                resampler = T.Resample(sr, model.samplerate).to(device)
                wav = resampler(wav)

            # Apply separation
            with torch.no_grad():
                # wav shape: [channels, time]
                # add batch dimension for demucs: [batch, channels, time]
                wav = wav.unsqueeze(0)
                sources = apply_model(model, wav, device=device, shifts=1, split=True, overlap=0.25)
                # sources shape: [batch, sources, channels, time]
                sources = sources.squeeze(0).cpu()  # Remove batch dimension

            # Get source names from the model
            # For htdemucs: drums, bass, other, vocals
            sources_dict = {}
            for i, src_name in enumerate(model.sources):
                sources_dict[src_name] = sources[i]

            kwargs = {
                "samplerate": model.samplerate, "bitrate": 128, "preset": 2,
                "clip": "rescale", "as_float": False, "bits_per_sample": 16
            }

            # Save vocals
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_v:
                vocals_path = tmp_v.name
            save_audio(sources_dict['vocals'], vocals_path, **kwargs)

            # Save background (everything except vocals)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_b:
                bg_path = tmp_b.name
            background = sum(sources_dict[src] for src in sources_dict if src != 'vocals')
            save_audio(background, bg_path, **kwargs)
            
            # Encode to base64
            vocals_base64 = None
            background_base64 = None
            
            if return_files:
                with open(vocals_path, 'rb') as f:
                    vocals_base64 = base64.b64encode(f.read()).decode('utf-8')
                with open(bg_path, 'rb') as f:
                    background_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            # Cleanup
            del sources, sources_dict, background
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
            
            processing_time = time.time() - start_time
            
            for f in [input_path, vocals_path, bg_path]:
                try:
                    os.unlink(f)
                except:
                    pass
            
            return SeparationResponse(
                success=True, vocals_base64=vocals_base64,
                background_base64=background_base64,
                processing_time=processing_time, device=device
            )
            
        finally:
            try:
                os.unlink(input_path)
            except:
                pass
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== Main Routes ==============

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check for all services"""
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
        whisper_models_loaded=list(whisper_model_cache.keys()),
        demucs_model_loaded='htdemucs' in demucs_model_cache,
        services={
            "asr": {"available": True, "endpoint": "/asr/transcribe"},
            "separation": {"available": DEMUC_AVAILABLE, "endpoint": "/separation/separate"}
        },
        platform=platform_str
    )

@app.delete("/cache")
async def clear_cache():
    """Clear all model caches"""
    whisper_model_cache.clear()
    demucs_model_cache.clear()
    if device == "cuda":
        torch.cuda.empty_cache()
    return {"status": "All caches cleared"}

# Include routers
app.include_router(asr_router)
app.include_router(separation_router)

# ============== Main ==============

def run_server(host="0.0.0.0", port=8000):
    """Run the server (for programmatic use)"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Optional ngrok support
    ngrok_token = os.environ.get("NGROK_TOKEN") or os.environ.get("NGROK_AUTHTOKEN")
    if ngrok_token:
        try:
            from pyngrok import ngrok, conf
            print(f"🌐 Setting up ngrok tunnel on port {port}...")
            conf.get_default().auth_token = ngrok_token
            
            # Kill any existing tunnels
            try:
                ngrok.kill()
            except:
                pass
                
            public_url = ngrok.connect(port).public_url
            print(f"\n🚀 Server is public at: {public_url}")
            print("\nTo use this with VideoLingo, update your config.yaml:")
            print("  whisper:")
            print("    runtime: cloud")
            print(f"    whisperX_cloud_url: {public_url}")
            print("  demucs: cloud\n")
        except ImportError:
            print("⚠️ pyngrok not installed, skipping ngrok tunnel setup.")
        except Exception as e:
            print(f"❌ Failed to start ngrok tunnel: {e}")

    run_server(host=host, port=port)
