import platform
import subprocess

import cv2
import numpy as np
from rich.console import Console

from core._1_ytdlp import find_video_files
from core.asr_backend.audio_preprocess import normalize_audio_volume
from core.utils import *
from core.utils.models import *
from core.utils.ffmpeg_utils import (
    build_ffmpeg_command, get_cpu_count, get_video_codec_args,
    get_audio_codec_args, get_output_optimization_args, run_ffmpeg_with_progress
)

console = Console()

DUB_VIDEO = "output/output_dub.mp4"
DUB_SUB_FILE = 'output/dub.srt'
DUB_AUDIO = 'output/dub.mp3'

TRANS_FONT_SIZE = 17
TRANS_FONT_NAME = 'Arial'
if platform.system() == 'Linux':
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'
if platform.system() == 'Darwin':
    TRANS_FONT_NAME = 'Arial Unicode MS'

TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1 
TRANS_BACK_COLOR = '&H33000000'

def merge_video_audio():
    """Merge video and audio, and reduce video volume with optimized performance"""
    VIDEO_FILE = find_video_files()
    background_file = _BACKGROUND_AUDIO_FILE

    # Normalize dub audio
    normalized_dub_audio = 'output/normalized_dub.wav'
    normalize_audio_volume(DUB_AUDIO, normalized_dub_audio)

    # Get video resolution
    video = cv2.VideoCapture(VIDEO_FILE)
    TARGET_WIDTH = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    TARGET_HEIGHT = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    rprint(f"[bold green]Video resolution: {TARGET_WIDTH}x{TARGET_HEIGHT}[/bold green]")

    # Get CPU count for optimization
    cpu_count = get_cpu_count()
    rprint(f"[bold blue]Using {cpu_count} CPU threads for processing[/bold blue]")

    # Always merge video and audio
    # Build video filter: scale/pad + optional subtitles
    video_filter = (
        f'scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,'
        f'pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2'
    )

    # Add subtitle filter only if burn_subtitles is enabled
    if load_key("burn_subtitles"):
        rprint("[bold green]Burning subtitles into video...[/bold green]")
        subtitle_filter = (
            f"subtitles={DUB_SUB_FILE}:force_style='FontSize={TRANS_FONT_SIZE},"
            f"FontName={TRANS_FONT_NAME},PrimaryColour={TRANS_FONT_COLOR},"
            f"OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
            f"BackColour={TRANS_BACK_COLOR},Alignment=2,MarginV=27,BorderStyle=4'"
        )
        video_filter += f',{subtitle_filter}'

    use_gpu = load_key("ffmpeg_gpu", False)
    
    # Build optimized filter complex
    filter_complex = (
        f'[0:v]{video_filter}[v];'
        f'[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=3[aout]'
    )

    # Build optimized FFmpeg command
    cmd = ['ffmpeg', '-y']
    
    # Performance optimizations
    cmd.extend(['-threads', str(cpu_count)])
    
    # Add inputs
    cmd.extend(['-i', VIDEO_FILE, '-i', background_file, '-i', normalized_dub_audio])
    
    # Add filter complex
    cmd.extend(['-filter_complex', filter_complex])
    
    # Map streams
    cmd.extend(['-map', '[v]', '-map', '[aout]'])
    
    # Video codec with optimization
    if use_gpu:
        rprint("[bold green]Using GPU acceleration (NVENC)...[/bold green]")
        cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'fast', '-tune', 'hq'])
    else:
        rprint("[bold blue]Using CPU encoding with fast preset...[/bold blue]")
        cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-tune', 'fastdecode'])
    
    # Audio codec
    cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
    
    # Output optimizations for web playback
    cmd.extend(['-movflags', '+faststart', '-pix_fmt', 'yuv420p'])
    
    # Output file
    cmd.append(DUB_VIDEO)

    # Run with progress monitoring
    run_ffmpeg_with_progress(cmd, "Merging video and audio")
    rprint(f"[bold green]Video and audio successfully merged into {DUB_VIDEO}[/bold green]")

if __name__ == '__main__':
    merge_video_audio()
