"""
WhisperX Cloud API Server
Deploy whisperX as a standalone service on GPU cloud platforms (Colab, Kaggle, etc.)
Compatible with VideoLingo project
"""

import os
# Set matplotlib backend to Agg before importing any matplotlib-dependent libraries
os.environ['MPLBACKEND'] = 'Agg'

import io
import base64
import tempfile
import warnings
import time
from typing import Optional
from contextlib import asynccontextmanager

import torch
import whisperx
import librosa
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

warnings.filterwarnings("ignore")

# Global model cache
model_cache = {}
device = None
compute_type = None

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

class HealthResponse(BaseModel):
    status: str
    device: str
    cuda_available: bool
    gpu_memory: Optional[float] = None
    models_loaded: list

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup, cleanup on shutdown"""
    global device, compute_type
    
    # Detect device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        compute_type = "float16" if torch.cuda.is_bf16_supported() else "int8"
        print(f"🚀 Using GPU: {torch.cuda.get_device_name(0)}")
        print(f"💾 GPU Memory: {gpu_mem:.2f} GB")
        print(f"⚙️ Compute type: {compute_type}")
    else:
        compute_type = "int8"
        print("⚠️ CUDA not available, using CPU")
    
    yield
    
    # Cleanup
    print("Cleaning up models...")
    model_cache.clear()
    if torch.cuda.is_available():
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
        print(f"📥 Loading model: {model_name}...")
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
        print(f"✅ Model loaded: {model_name}")
    
    return model_cache[cache_key]

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
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    
    return HealthResponse(
        status="healthy",
        device=device,
        cuda_available=torch.cuda.is_available(),
        gpu_memory=gpu_mem,
        models_loaded=list(model_cache.keys())
    )

@app.post("/transcribe", response_model=TranscriptionResponse)
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
    
    # Determine batch size
    if batch_size is None:
        if device == "cuda":
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            batch_size = 16 if gpu_mem > 8 else 4
        else:
            batch_size = 1
    
    try:
        # Read audio file
        audio_bytes = await audio.read()
        audio_array = process_audio(audio_bytes)
        
        # Load model
        whisper_model = get_or_load_model(model, language, batch_size)
        
        # Transcribe
        print("🎯 Starting transcription...")
        result = whisper_model.transcribe(audio_array, batch_size=batch_size)
        detected_language = result.get("language", language or "unknown")
        segments = result.get("segments", [])
        
        # Word-level alignment
        word_segments = None
        if align and segments:
            print("🔄 Aligning words...")
            align_model, align_metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=device
            )
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
            del align_model
            torch.cuda.empty_cache()
        
        # Speaker diarization
        speakers = None
        if speaker_diarization:
            print("🎭 Performing speaker diarization...")
            diarize_model = whisperx.DiarizationPipeline(
                model_name="pyannote/speaker-diarization-3.1",
                device=device
            )
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
            model=model
        )
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
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

@app.delete("/cache")
async def clear_cache():
    """Clear model cache to free GPU memory"""
    global model_cache
    model_cache.clear()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {"status": "Cache cleared"}

if __name__ == "__main__":
    # For local testing
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
