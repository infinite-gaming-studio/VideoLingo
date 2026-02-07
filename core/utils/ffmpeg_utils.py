"""
FFmpeg performance optimization utilities
Provides optimized FFmpeg command builders with multi-threading and hardware acceleration
"""

import os
import subprocess
from typing import List, Optional, Dict
from core.utils import load_key

# CPU 核心数检测
def get_cpu_count() -> int:
    """Get number of CPU cores for threading"""
    return os.cpu_count() or 4

# FFmpeg 性能参数构建器
def build_ffmpeg_performance_args(use_gpu: Optional[bool] = None) -> List[str]:
    """
    Build FFmpeg performance arguments
    
    Args:
        use_gpu: Whether to use GPU acceleration (defaults to config value)
    
    Returns:
        List of FFmpeg arguments for performance optimization
    """
    if use_gpu is None:
        use_gpu = load_key("ffmpeg_gpu", False)
    
    args = []
    cpu_count = get_cpu_count()
    
    # Multi-threading for filters
    args.extend(['-threads', str(cpu_count)])
    
    return args

def get_video_codec_args(use_gpu: Optional[bool] = None) -> List[str]:
    """
    Get video codec arguments with hardware acceleration if available
    
    Args:
        use_gpu: Whether to use GPU acceleration
        
    Returns:
        List of codec-specific arguments
    """
    if use_gpu is None:
        use_gpu = load_key("ffmpeg_gpu", False)
    
    if use_gpu:
        # NVIDIA NVENC
        return ['-c:v', 'h264_nvenc', '-preset', 'fast', '-tune', 'hq']
    else:
        # CPU encoding with fast preset
        return ['-c:v', 'libx264', '-preset', 'fast', '-tune', 'fastdecode']

def get_audio_codec_args() -> List[str]:
    """Get optimized audio codec arguments"""
    return ['-c:a', 'aac', '-b:a', '128k']

def get_output_optimization_args() -> List[str]:
    """Get output file optimization arguments"""
    return ['-movflags', '+faststart', '-pix_fmt', 'yuv420p']

def build_ffmpeg_command(
    input_files: List[str],
    output_file: str,
    filter_complex: Optional[str] = None,
    video_filter: Optional[str] = None,
    use_gpu: Optional[bool] = None,
    extra_args: Optional[List[str]] = None
) -> List[str]:
    """
    Build a complete optimized FFmpeg command
    
    Args:
        input_files: List of input file paths
        output_file: Output file path
        filter_complex: Optional filter complex string
        video_filter: Optional video filter string
        use_gpu: Whether to use GPU acceleration
        extra_args: Additional FFmpeg arguments
        
    Returns:
        Complete FFmpeg command as list
    """
    cmd = ['ffmpeg', '-y']
    
    # Add performance arguments
    cmd.extend(build_ffmpeg_performance_args(use_gpu))
    
    # Add inputs
    for input_file in input_files:
        cmd.extend(['-i', input_file])
    
    # Add filters
    if filter_complex:
        cmd.extend(['-filter_complex', filter_complex])
    elif video_filter:
        cmd.extend(['-vf', video_filter])
    
    # Add codec and optimization args
    cmd.extend(get_video_codec_args(use_gpu))
    cmd.extend(get_audio_codec_args())
    cmd.extend(get_output_optimization_args())
    
    # Add extra args
    if extra_args:
        cmd.extend(extra_args)
    
    # Add output
    cmd.append(output_file)
    
    return cmd

def run_ffmpeg_with_progress(cmd: List[str], description: str = "Processing") -> None:
    """
    Run FFmpeg command with progress monitoring
    
    Args:
        cmd: FFmpeg command as list
        description: Description for progress display
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    console = Console()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"[cyan]{description}...", total=None)
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                console.print(f"[red]FFmpeg error: {result.stderr}[/red]")
                raise subprocess.CalledProcessError(result.returncode, cmd)
                
        except Exception as e:
            console.print(f"[red]Error during FFmpeg execution: {e}[/red]")
            raise
