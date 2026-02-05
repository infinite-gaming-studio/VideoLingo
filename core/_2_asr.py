"""
VideoLingo ASR Transcription Module
Main entry point for audio transcription pipeline

Cloud Native Mode:
- When cloud_native.enabled=true in config.yaml
- All AI processing (ASR + Demucs) uses remote cloud services
- Local processing includes: FFmpeg, pydub, spacy (lightweight)

Legacy Mode:
- Supports local GPU, 302 API, or ElevenLabs API for ASR
- Supports local or cloud for Demucs
"""

from core.utils import *
from core.asr_backend.demucs_vl import demucs_audio
from core.asr_backend.audio_preprocess import process_transcription, convert_video_to_audio, split_audio, save_results, normalize_audio_volume
from core._1_ytdlp import find_video_files
from core.utils.models import *


def is_cloud_native():
    """Check if cloud native mode is enabled"""
    return load_key("cloud_native.enabled", False)


def check_cloud_native_prerequisites():
    """Check if cloud native prerequisites are met"""
    if not is_cloud_native():
        return True
    
    cloud_url = load_key("cloud_native.cloud_url", "")
    if not cloud_url:
        raise ValueError(
            "Cloud Native Mode is enabled but cloud_native.cloud_url is not configured.\n"
            "Please deploy the unified cloud server and set the URL in config.yaml"
        )
    
    # Try to import and check cloud client
    try:
        from whisperx_cloud.unified_client import check_cloud_connection
        result = check_cloud_connection(cloud_url)
        if not result.get('available'):
            raise ConnectionError(
                f"Cannot connect to cloud service at {cloud_url}\n"
                f"Error: {result.get('error', 'Unknown error')}"
            )
        rprint(f"[green]✅ Cloud Native Mode: Connected to {cloud_url}[/green]")
    except ImportError:
        raise ImportError(
            "Cloud Native Mode requires whisperx_cloud module.\n"
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
    if is_cloud_native():
        from core.asr_backend.whisperX_asr import transcribe_audio as ts
        rprint("[cyan]☁️ Transcribing audio with Cloud Native ASR...[/cyan]")
    elif runtime == "local":
        from core.asr_backend.whisperX_asr import transcribe_audio as ts
        rprint("[cyan]🎤 Transcribing audio with local model...[/cyan]")
    elif runtime == "cloud":
        from core.asr_backend.whisperX_302 import transcribe_audio_302 as ts
        rprint("[cyan]🎤 Transcribing audio with 302 API...[/cyan]")
    elif runtime == "elevenlabs":
        from core.asr_backend.elevenlabs_asr import transcribe_audio_elevenlabs as ts
        rprint("[cyan]🎤 Transcribing audio with ElevenLabs API...[/cyan]")

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