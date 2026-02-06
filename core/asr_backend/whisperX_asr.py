"""
VideoLingo WhisperX ASR Module
Supports cloud-native remote processing only.

Cloud Native Mode:
- When whisper.runtime='cloud' in config.yaml
- All ASR processing is done via remote WhisperX cloud service
- No local torch/whisperx dependencies required
"""

import os
import warnings
import time
from rich import print as rprint
from core.utils import *

def is_cloud_native():
    """Check if cloud native mode is enabled in config
    Uses runtime='cloud'"""
    try:
        # Cloud mode is enabled when runtime='cloud'
        if load_key("whisper.runtime", "") == "cloud":
            return True
        return False
    except:
        # Default to False if config load fails, though usually configured
        return False

# Local dependencies removed.

MODEL_DIR = load_key("model_dir")

@except_handler("WhisperX processing error:")
def transcribe_audio(raw_audio_file, vocal_audio_file, start, end):
    """
    Transcribe audio segment using WhisperX (Cloud Mode Only)
    
    In Cloud Native Mode:
    - Sends audio to remote WhisperX cloud service
    - Returns transcription results
    """
    # Force cloud native check or just proceed if called (assuming caller checked)
    # But for safety, we allow it to proceed as cloud.
    return transcribe_audio_cloud(raw_audio_file, vocal_audio_file, start, end)


def transcribe_audio_cloud(raw_audio_file, vocal_audio_file, start, end):
    """
    Cloud-native ASR processing via unified cloud client
    Sends audio segment to remote WhisperX service
    """
    from videolingo_cloud.videolingo_cloud_client import transcribe_audio_cloud_compatible
    
    vprint(f"[cyan]☁️ Using Cloud Native ASR for segment {start:.2f}s to {end:.2f}s...[/cyan]")
    
    result = transcribe_audio_cloud_compatible(
        raw_audio_file=raw_audio_file,
        vocal_audio_file=vocal_audio_file,
        start=start,
        end=end
    )
    
    return result
