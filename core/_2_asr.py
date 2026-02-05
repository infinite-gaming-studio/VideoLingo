"""
VideoLingo ASR Transcription Module
Main entry point for audio transcription pipeline

Cloud Native Mode:
- When whisper.runtime='cloud' in config.yaml
- All AI processing (ASR + Demucs) uses remote cloud services
- Local processing includes: FFmpeg, pydub, spacy (lightweight)

Legacy Mode:
- Supports local GPU or ElevenLabs API for ASR
- Supports local or cloud for Demucs
"""

from core.utils import *
from core.asr_backend.demucs_vl import demucs_audio
from core.asr_backend.audio_preprocess import process_transcription, convert_video_to_audio, split_audio, save_results, normalize_audio_volume
from core._1_ytdlp import find_video_files
from core.utils.models import *


def is_cloud_native():
    """Check if cloud native mode is enabled
    Uses runtime='cloud' in config.yaml"""
    # Cloud mode is enabled when runtime='cloud'
    if load_key("whisper.runtime", "") == "cloud":
        return True
    return False


def check_cloud_native_prerequisites():
    """Check if cloud native prerequisites are met"""
    if not is_cloud_native():
        return True
    
    # Use unified cloud client to get URL
    try:
        from whisperx_cloud.unified_client import get_cloud_url, check_cloud_connection
        cloud_url = get_cloud_url()
        
        if not cloud_url:
            raise ValueError(
                "Cloud Mode is enabled but cloud URL is not configured.\n"
                "Please set cloud_native.cloud_url in config.yaml"
            )
        
        result = check_cloud_connection(cloud_url)
        if not result.get('available'):
            raise ConnectionError(
                f"Cannot connect to cloud service at {cloud_url}\n"
                f"Error: {result.get('error', 'Unknown error')}"
            )
        rprint(f"[green]✅ Cloud Mode: Connected to {cloud_url}[/green]")
    except ImportError:
        raise ImportError(
            "Cloud Mode requires whisperx_cloud module.\n"
            "Please ensure whisperx_cloud/ directory is in the project root."
        )
    
    return True


@check_file_exists(_2_CLEANED_CHUNKS)
def transcribe():
    # Check cloud native prerequisites
    if is_cloud_native():
        check_cloud_native_prerequisites()
        rprint("[bold cyan]☁️ Running in Cloud Native Mode - All AI processing via remote services[/bold cyan]")
    
    # 1. video to audio (local - lightweight)
    video_file = find_video_files()
    convert_video_to_audio(video_file)

    # 2. Demucs vocal separation (cloud or local based on config)
    demucs_mode = load_key("demucs")
    if demucs_mode and demucs_mode != False:
        if is_cloud_native():
            rprint("[cyan]☁️ Using cloud Demucs for vocal separation...[/cyan]")
        demucs_audio()
        vocal_audio = normalize_audio_volume(_VOCAL_AUDIO_FILE, _VOCAL_AUDIO_FILE, format="mp3")
    else:
        vocal_audio = _RAW_AUDIO_FILE

    # 3. Extract audio segments (local - lightweight)
    segments = split_audio(_RAW_AUDIO_FILE)

    # 4. Transcribe audio by clips
    all_results = []
    runtime = load_key("whisper.runtime")
    
    # In Cloud Native Mode, force using whisperX_asr which supports cloud
    # Also support legacy runtime="cloud" for backward compatibility
    if is_cloud_native() or runtime == "cloud":
        from core.asr_backend.whisperX_asr import transcribe_audio as ts
        rprint("[cyan]☁️ Transcribing audio with Cloud Native ASR...[/cyan]")
    elif runtime == "local":
        from core.asr_backend.whisperX_asr import transcribe_audio as ts
        rprint("[cyan]🎤 Transcribing audio with local model...[/cyan]")
    elif runtime == "elevenlabs":
        from core.asr_backend.elevenlabs_asr import transcribe_audio_elevenlabs as ts
        rprint("[cyan]🎤 Transcribing audio with ElevenLabs API...[/cyan]")
    else:
        raise ValueError(f"Unsupported whisper.runtime: {runtime}. Use 'local', 'elevenlabs', or enable cloud_native mode.")

    for start, end in segments:
        result = ts(_RAW_AUDIO_FILE, vocal_audio, start, end)
        all_results.append(result)

    # 5. Combine results (local)
    combined_result = {'segments': []}
    for result in all_results:
        combined_result['segments'].extend(result['segments'])

    # 6. Process df (local - lightweight)
    df = process_transcription(combined_result)
    save_results(df)
    
    if is_cloud_native():
        rprint("[bold green]✅ Cloud Native transcription completed![/bold green]")
        
if __name__ == "__main__":
    transcribe()