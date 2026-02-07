import os, subprocess, time
from core._1_ytdlp import find_video_files
import cv2
import numpy as np
import platform
from core.utils import *
from core.utils.ffmpeg_utils import get_cpu_count, run_ffmpeg_with_progress

SRC_FONT_SIZE = 15
TRANS_FONT_SIZE = 17
FONT_NAME = 'Arial'
TRANS_FONT_NAME = 'Arial'

# Linux need to install google noto fonts: apt-get install fonts-noto
if platform.system() == 'Linux':
    FONT_NAME = 'NotoSansCJK-Regular'
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'
# Mac OS has different font names
elif platform.system() == 'Darwin':
    FONT_NAME = 'Arial Unicode MS'
    TRANS_FONT_NAME = 'Arial Unicode MS'

SRC_FONT_COLOR = '&HFFFFFF'
SRC_OUTLINE_COLOR = '&H000000'
SRC_OUTLINE_WIDTH = 1
SRC_SHADOW_COLOR = '&H80000000'
TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1 
TRANS_BACK_COLOR = '&H33000000'

OUTPUT_DIR = "output"
OUTPUT_VIDEO = f"{OUTPUT_DIR}/output_sub.mp4"
SRC_SRT = f"{OUTPUT_DIR}/src.srt"
TRANS_SRT = f"{OUTPUT_DIR}/trans.srt"
    
def check_gpu_available():
    try:
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        return 'h264_nvenc' in result.stdout
    except:
        return False

def merge_subtitles_to_video():
    video_file = find_video_files()
    os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

    # Check resolution
    if not load_key("burn_subtitles"):
        rprint("[bold yellow]Warning: A 0-second black video will be generated as a placeholder as subtitles are not burned in.[/bold yellow]")

        # Create a black frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, 1, (1920, 1080))
        out.write(frame)
        out.release()

        rprint("[bold green]Placeholder video has been generated.[/bold green]")
        return

    if not os.path.exists(SRC_SRT) or not os.path.exists(TRANS_SRT):
        rprint("Subtitle files not found in the 'output' directory.")
        exit(1)

    video = cv2.VideoCapture(video_file)
    TARGET_WIDTH = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    TARGET_HEIGHT = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    rprint(f"[bold green]Video resolution: {TARGET_WIDTH}x{TARGET_HEIGHT}[/bold green]")

    # Get CPU count for optimization
    cpu_count = get_cpu_count()
    rprint(f"[bold blue]Using {cpu_count} CPU threads for processing[/bold blue]")

    # Build optimized FFmpeg command
    ffmpeg_cmd = ['ffmpeg', '-y']
    
    # Performance optimizations
    ffmpeg_cmd.extend(['-threads', str(cpu_count)])
    
    # Input
    ffmpeg_cmd.extend(['-i', video_file])
    
    # Video filter with dual subtitles
    video_filter = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"subtitles={SRC_SRT}:force_style='FontSize={SRC_FONT_SIZE},FontName={FONT_NAME},"
        f"PrimaryColour={SRC_FONT_COLOR},OutlineColour={SRC_OUTLINE_COLOR},OutlineWidth={SRC_OUTLINE_WIDTH},"
        f"ShadowColour={SRC_SHADOW_COLOR},BorderStyle=1',"
        f"subtitles={TRANS_SRT}:force_style='FontSize={TRANS_FONT_SIZE},FontName={TRANS_FONT_NAME},"
        f"PrimaryColour={TRANS_FONT_COLOR},OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
        f"BackColour={TRANS_BACK_COLOR},Alignment=2,MarginV=27,BorderStyle=4'"
    )
    ffmpeg_cmd.extend(['-vf', video_filter])

    # Video codec with optimization
    ffmpeg_gpu = load_key("ffmpeg_gpu")
    if ffmpeg_gpu:
        rprint("[bold green]Using GPU acceleration (NVENC)...[/bold green]")
        ffmpeg_cmd.extend(['-c:v', 'h264_nvenc', '-preset', 'fast', '-tune', 'hq'])
    else:
        rprint("[bold blue]Using CPU encoding with fast preset...[/bold blue]")
        ffmpeg_cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-tune', 'fastdecode'])
    
    # Copy audio stream (no re-encoding for speed)
    ffmpeg_cmd.extend(['-c:a', 'copy'])
    
    # Output optimizations for web playback
    ffmpeg_cmd.extend(['-movflags', '+faststart', '-pix_fmt', 'yuv420p'])
    
    # Output file
    ffmpeg_cmd.append(OUTPUT_VIDEO)

    rprint("🎬 Start merging subtitles to video...")
    start_time = time.time()
    
    # Run with progress monitoring
    run_ffmpeg_with_progress(ffmpeg_cmd, "Merging subtitles to video")
    
    rprint(f"\n✅ Done! Time taken: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    merge_subtitles_to_video()