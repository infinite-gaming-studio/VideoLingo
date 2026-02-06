"""
Demucs Cloud API Server
Deploy Demucs vocal separation as a standalone service on GPU cloud platforms (Colab, Kaggle, etc.)
Compatible with VideoLingo project
"""

# Server version
SERVER_VERSION = "1.1.0"

import os
import io
import base64
import tempfile
import warnings
import time
import torch
import torchaudio
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from demucs.pretrained import get_model
from demucs.audio import save_audio
from demucs.api import Separator
from demucs.apply import BagOfModels
import gc

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

# Global model cache
model_cache = {}
device = None

class PreloadedSeparator(Separator):
    """Custom Separator with preloaded model"""
    def __init__(self, model: BagOfModels, shifts: int = 1, overlap: float = 0.25,
                 split: bool = True, segment: Optional[int] = None, jobs: int = 0):
        self._model, self._audio_channels, self._samplerate = model, model.audio_channels, model.samplerate
        self.update_parameter(device=device, shifts=shifts, overlap=overlap, split=split,
                            segment=segment, jobs=jobs, progress=True, callback=None, callback_arg=None)

def get_device():
    """智能设备检测: CUDA -> MPS (Apple Silicon) -> CPU"""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    else:
        return "cpu"

def get_or_load_model():
    """Load or retrieve cached Demucs model"""
    global model_cache
    
    if 'htdemucs' not in model_cache:
        vprint("📥 Loading Demucs htdemucs model...")
        model = get_model('htdemucs')
        model_cache['htdemucs'] = model
        vprint("✅ Demucs model loaded")
    
    return model_cache['htdemucs']

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
    model_loaded: bool
    server_version: str = SERVER_VERSION
    platform: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup, cleanup on shutdown"""
    global device

    # Print server version on startup
    vprint(f"📌 Demucs Cloud Server v{SERVER_VERSION}\n")

    # Detect device
    device = get_device()
    
    if device == "cuda":
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        vprint(f"🚀 Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        vprint(f"💾 GPU Memory: {gpu_mem:.2f} GB")
    elif device == "mps":
        vprint(f"🍎 Using Apple Silicon MPS")
    else:
        vprint("💻 Using CPU (no GPU detected)")

    # Preload model
    get_or_load_model()

    yield

    # Cleanup
    vprint("Cleaning up models...")
    model_cache.clear()
    if device == "cuda":
        torch.cuda.empty_cache()

app = FastAPI(
    title="Demucs Cloud API",
    description="Standalone Demucs vocal separation service for VideoLingo",
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
        model_loaded='htdemucs' in model_cache,
        platform=platform_str
    )

@app.post("/separate", response_model=SeparationResponse)
async def separate_audio(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, m4a, etc.)"),
    return_files: bool = True
):
    """
    Separate audio into vocals and background using Demucs
    
    Args:
        audio: Audio file to process
        return_files: If True, return base64-encoded audio files in response
    
    Returns:
        SeparationResponse with base64-encoded vocals and background audio
    """
    start_time = time.time()
    
    try:
        # Read audio file
        audio_bytes = await audio.read()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_input:
            tmp_input.write(audio_bytes)
            input_path = tmp_input.name
        
        try:
            # Load model
            model = get_or_load_model()
            separator = PreloadedSeparator(model=model, shifts=1, overlap=0.25)
            
            # Separate audio
            vprint("🎵 Separating audio...")
            _, outputs = separator.separate_audio_file(input_path)
            
            # Prepare kwargs for saving
            kwargs = {
                "samplerate": model.samplerate, 
                "bitrate": 128, 
                "preset": 2, 
                "clip": "rescale", 
                "as_float": False, 
                "bits_per_sample": 16
            }
            
            # Save vocals to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_vocals:
                vocals_path = tmp_vocals.name
            save_audio(outputs['vocals'].cpu(), vocals_path, **kwargs)
            
            # Save background to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_bg:
                bg_path = tmp_bg.name
            background = sum(audio for source, audio in outputs.items() if source != 'vocals')
            save_audio(background.cpu(), bg_path, **kwargs)
            
            # Read files and encode to base64
            vocals_base64 = None
            background_base64 = None
            
            if return_files:
                with open(vocals_path, 'rb') as f:
                    vocals_base64 = base64.b64encode(f.read()).decode('utf-8')
                with open(bg_path, 'rb') as f:
                    background_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            # Cleanup
            del outputs, background, separator
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
            
            processing_time = time.time() - start_time
            
            # Cleanup temp files
            for f in [input_path, vocals_path, bg_path]:
                try:
                    os.unlink(f)
                except:
                    pass
            
            return SeparationResponse(
                success=True,
                vocals_base64=vocals_base64,
                background_base64=background_base64,
                processing_time=processing_time,
                device=device
            )
            
        finally:
            # Cleanup input temp file
            try:
                os.unlink(input_path)
            except:
                pass
                
    except Exception as e:
        vprint(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/separate/url")
async def separate_audio_url(
    audio_url: str,
    return_files: bool = True
):
    """
    Separate audio from URL
    
    Args:
        audio_url: URL to audio file
        return_files: If True, return base64-encoded audio files
    """
    import requests
    
    start_time = time.time()
    
    try:
        # Download audio from URL
        response = requests.get(audio_url, timeout=30)
        response.raise_for_status()
        audio_bytes = response.content
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_input:
            tmp_input.write(audio_bytes)
            input_path = tmp_input.name
        
        try:
            # Load model
            model = get_or_load_model()
            separator = PreloadedSeparator(model=model, shifts=1, overlap=0.25)
            
            # Separate audio
            vprint(f"🎵 Separating audio from URL...")
            _, outputs = separator.separate_audio_file(input_path)
            
            # Prepare kwargs for saving
            kwargs = {
                "samplerate": model.samplerate, 
                "bitrate": 128, 
                "preset": 2, 
                "clip": "rescale", 
                "as_float": False, 
                "bits_per_sample": 16
            }
            
            # Save vocals to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_vocals:
                vocals_path = tmp_vocals.name
            save_audio(outputs['vocals'].cpu(), vocals_path, **kwargs)
            
            # Save background to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_bg:
                bg_path = tmp_bg.name
            background = sum(audio for source, audio in outputs.items() if source != 'vocals')
            save_audio(background.cpu(), bg_path, **kwargs)
            
            # Read files and encode to base64
            vocals_base64 = None
            background_base64 = None
            
            if return_files:
                with open(vocals_path, 'rb') as f:
                    vocals_base64 = base64.b64encode(f.read()).decode('utf-8')
                with open(bg_path, 'rb') as f:
                    background_base64 = base64.b64encode(f.read()).decode('utf-8')
            
            # Cleanup
            del outputs, background, separator
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
            
            processing_time = time.time() - start_time
            
            # Cleanup temp files
            for f in [input_path, vocals_path, bg_path]:
                try:
                    os.unlink(f)
                except:
                    pass
            
            return {
                "success": True,
                "vocals_base64": vocals_base64,
                "background_base64": background_base64,
                "processing_time": processing_time,
                "device": device,
                "server_version": SERVER_VERSION
            }
            
        finally:
            # Cleanup input temp file
            try:
                os.unlink(input_path)
            except:
                pass
                
    except Exception as e:
        vprint(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/cache")
async def clear_cache():
    """Clear model cache to free GPU memory"""
    global model_cache
    model_cache.clear()
    if device == "cuda":
        torch.cuda.empty_cache()
    return {"status": "Cache cleared"}

if __name__ == "__main__":
    # For local testing
    port = int(os.environ.get("PORT", 8001))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
