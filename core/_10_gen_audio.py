import os
import time
import shutil
import subprocess
from typing import Tuple

import pandas as pd
from pydub import AudioSegment
from rich.console import Console
from rich.progress import Progress
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.utils import *
from core.utils.models import *
from core.asr_backend.audio_preprocess import get_audio_duration
from core.tts_backend.tts_main import tts_main

console = Console()

TEMP_FILE_TEMPLATE = f"{_AUDIO_TMP_DIR}/{{}}_temp.wav"
OUTPUT_FILE_TEMPLATE = f"{_AUDIO_SEGS_DIR}/{{}}.wav"
WARMUP_SIZE = 5

def parse_df_srt_time(time_str: str) -> float:
    """Convert SRT time format to seconds"""
    hours, minutes, seconds = time_str.strip().split(':')
    seconds, milliseconds = seconds.split('.')
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000

def adjust_audio_speed(input_file: str, output_file: str, speed_factor: float) -> None:
    """Adjust audio speed with optimized FFmpeg and handle edge cases"""
    import os
    cpu_count = os.cpu_count() or 4
    
    # If the speed factor is close to 1, directly copy the file
    if abs(speed_factor - 1.0) < 0.001:
        shutil.copy2(input_file, output_file)
        return
    
    # Validate speed factor (atempo supports 0.5 to 2.0)
    atempo = max(0.5, min(2.0, speed_factor))
    if atempo != speed_factor:
        rprint(f"[yellow]⚠️ Speed factor adjusted from {speed_factor} to {atempo} (FFmpeg atempo limit)[/yellow]")
    
    # Build optimized FFmpeg command
    cmd = [
        'ffmpeg', '-y', '-threads', str(min(4, cpu_count)),
        '-i', input_file,
        '-filter:a', f'atempo={atempo}',
        '-c:a', 'pcm_s16le',  # Use PCM for lossless audio
        '-ar', '16000', '-ac', '1',
        output_file
    ]
    
    input_duration = get_audio_duration(input_file)
    max_retries = 2
    for attempt in range(max_retries):
        try:
            subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
            output_duration = get_audio_duration(output_file)
            expected_duration = input_duration / atempo
            diff = output_duration - expected_duration
            
            # If the output duration exceeds the expected duration, but the input audio is less than 3 seconds, and the error is within 0.1 seconds, truncate to the expected length
            if output_duration >= expected_duration * 1.02 and input_duration < 3 and diff <= 0.1:
                audio = AudioSegment.from_wav(output_file)
                trimmed_audio = audio[:(expected_duration * 1000)]  # pydub uses milliseconds
                trimmed_audio.export(output_file, format="wav")
                print(f"✂️ Trimmed to expected duration: {expected_duration:.2f} seconds")
                return
            elif output_duration >= expected_duration * 1.02:
                raise Exception(f"Audio duration abnormal: input file={input_file}, output file={output_file}, speed factor={atempo}, input duration={input_duration:.2f}s, output duration={output_duration:.2f}s")
            return
        except subprocess.CalledProcessError as e:
            if attempt < max_retries - 1:
                rprint(f"[yellow]⚠️ Audio speed adjustment failed, retrying in 1s ({attempt + 1}/{max_retries})[/yellow]")
                time.sleep(1)
            else:
                rprint(f"[red]❌ Audio speed adjustment failed, max retries reached ({max_retries})[/red]")
                raise e

def process_row(row: pd.Series, tasks_df: pd.DataFrame) -> Tuple[int, float]:
    """Helper function for processing single row data"""
    number = row['number']
    lines = eval(row['lines']) if isinstance(row['lines'], str) else row['lines']
    real_dur = 0
    for line_index, line in enumerate(lines):
        temp_file = TEMP_FILE_TEMPLATE.format(f"{number}_{line_index}")
        tts_main(line, temp_file, number, tasks_df)
        real_dur += get_audio_duration(temp_file)
    return number, real_dur

def generate_tts_audio(tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Generate TTS audio sequentially and calculate actual duration"""
    tasks_df['real_dur'] = 0
    rprint("[bold green]🎯 Starting TTS audio generation...[/bold green]")
    
    with Progress() as progress:
        task = progress.add_task("[cyan]🔄 Generating TTS audio...", total=len(tasks_df))
        
        # warm up for first 5 rows
        warmup_size = min(WARMUP_SIZE, len(tasks_df))
        for _, row in tasks_df.head(warmup_size).iterrows():
            try:
                number, real_dur = process_row(row, tasks_df)
                tasks_df.loc[tasks_df['number'] == number, 'real_dur'] = real_dur
                progress.advance(task)
            except Exception as e:
                rprint(f"[red]❌ Error in warmup: {str(e)}[/red]")
                raise e
        
        # for gpt_sovits and indextts, do not use parallel to avoid mistakes
        tts_method = load_key("tts_method")
        if tts_method in ["gpt_sovits", "indextts"]:
            max_workers = 1
        else:
            max_workers = load_key("max_workers")
        # parallel processing for remaining tasks
        if len(tasks_df) > warmup_size:
            remaining_tasks = tasks_df.iloc[warmup_size:].copy()
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(process_row, row, tasks_df.copy())
                    for _, row in remaining_tasks.iterrows()
                ]
                
                for future in as_completed(futures):
                    try:
                        number, real_dur = future.result()
                        tasks_df.loc[tasks_df['number'] == number, 'real_dur'] = real_dur
                        progress.advance(task)
                    except Exception as e:
                        rprint(f"[red]❌ Error: {str(e)}[/red]")
                        raise e

    rprint("[bold green]✨ TTS audio generation completed![/bold green]")
    return tasks_df

def process_chunk(chunk_df: pd.DataFrame, accept: float, min_speed: float) -> tuple[float, bool]:
    """Process audio chunk and calculate speed factor"""
    chunk_durs = chunk_df['real_dur'].sum()
    tol_durs = chunk_df['tol_dur'].sum()
    durations = tol_durs - chunk_df.iloc[-1]['tolerance']
    all_gaps = chunk_df['gap'].sum() - chunk_df.iloc[-1]['gap']
    
    keep_gaps = True
    speed_var_error = 0.1

    if (chunk_durs + all_gaps) / accept < durations:
        speed_factor = max(min_speed, (chunk_durs + all_gaps) / (durations-speed_var_error))
    elif chunk_durs / accept < durations:
        speed_factor = max(min_speed, chunk_durs / (durations-speed_var_error))
        keep_gaps = False
    elif (chunk_durs + all_gaps) / accept < tol_durs:
        speed_factor = max(min_speed, (chunk_durs + all_gaps) / (tol_durs-speed_var_error))
    else:
        speed_factor = chunk_durs / (tol_durs-speed_var_error)
        keep_gaps = False
        
    return round(speed_factor, 3), keep_gaps

def compress_gaps(chunk_df: pd.DataFrame, overflow: float) -> float:
    """Compress gaps within chunk to absorb overflow time. Returns actually saved time."""
    if overflow <= 0 or len(chunk_df) <= 1:
        return 0.0
    
    # Calculate total compressible gap (exclude last gap)
    gaps = chunk_df['gap'].tolist()
    total_gap = sum(gaps[:-1]) if len(gaps) > 1 else 0
    
    if total_gap < 0.1:  # No meaningful gap to compress
        return 0.0
    
    # Calculate compression ratio (keep at least 30% of original gap)
    max_compressible = total_gap * 0.7  # Can compress up to 70%
    actual_compress = min(overflow, max_compressible)
    
    if actual_compress <= 0:
        return 0.0
    
    # Apply proportional compression to all gaps
    compression_ratio = 1 - (actual_compress / total_gap)
    chunk_df['gap'] = chunk_df['gap'] * compression_ratio
    
    rprint(f"[cyan]📉 Compressed gaps by {(1-compression_ratio)*100:.1f}%, saved {actual_compress:.3f}s[/cyan]")
    return actual_compress


def merge_chunks(tasks_df: pd.DataFrame) -> pd.DataFrame:
    """Merge audio chunks without truncation - use gap compression and video compensation instead"""
    rprint("[bold blue]🔄 Starting audio chunks processing...[/bold blue]")
    accept = load_key("speed_factor.accept")
    min_speed = load_key("speed_factor.min")
    chunk_start = 0
    
    tasks_df['new_sub_times'] = None
    compensation_map = []  # Track video compensation needs
    
    for index, row in tasks_df.iterrows():
        if row['cut_off'] == 1:
            chunk_df = tasks_df.iloc[chunk_start:index+1].reset_index(drop=True)
            speed_factor, keep_gaps = process_chunk(chunk_df, accept, min_speed)
            
            # Calculate time targets
            chunk_start_time = parse_df_srt_time(chunk_df.iloc[0]['start_time'])
            chunk_end_time = parse_df_srt_time(chunk_df.iloc[-1]['end_time']) + chunk_df.iloc[-1]['tolerance']
            target_duration = chunk_end_time - chunk_start_time
            
            # 🎯 NEW: Limit voice speed to 1.15x for naturalness
            max_voice_speed = 1.15
            actual_speed = min(speed_factor, max_voice_speed)
            
            cur_time = chunk_start_time
            total_audio_duration = 0.0
            
            for i, row in chunk_df.iterrows():
                if i != 0 and keep_gaps:
                    cur_time += chunk_df.iloc[i-1]['gap'] / actual_speed
                
                new_sub_times = []
                number = row['number']
                lines = eval(row['lines']) if isinstance(row['lines'], str) else row['lines']
                
                for line_index, line in enumerate(lines):
                    temp_file = TEMP_FILE_TEMPLATE.format(f"{number}_{line_index}")
                    output_file = OUTPUT_FILE_TEMPLATE.format(f"{number}_{line_index}")
                    adjust_audio_speed(temp_file, output_file, actual_speed)
                    ad_dur = get_audio_duration(output_file)
                    new_sub_times.append([cur_time, cur_time + ad_dur])
                    cur_time += ad_dur
                    total_audio_duration += ad_dur
                
                main_df_idx = tasks_df[tasks_df['number'] == row['number']].index[0]
                tasks_df.at[main_df_idx, 'new_sub_times'] = new_sub_times
            
            # 🎯 NEW: Check overflow and apply gap compression
            overflow = cur_time - chunk_end_time
            
            if overflow > 0:
                rprint(f"[yellow]⚠️ Chunk {chunk_start} to {index} would exceed by {overflow:.3f}s[/yellow]")
                
                # Strategy 1: Compress gaps
                saved_time = compress_gaps(chunk_df, overflow)
                overflow -= saved_time
                
                # Strategy 2: If still overflow, mark for video compensation
                if overflow > 0.1:  # More than 100ms needs compensation
                    # When audio is longer than target, video needs to SLOW DOWN
                    # to match the longer audio duration
                    # target_duration = original_duration (chunk duration)
                    # audio_duration = target_duration + overflow
                    # speed = target_duration / audio_duration
                    audio_duration = target_duration + overflow
                    video_speed = target_duration / audio_duration
                    video_speed = max(0.92, min(1.0, video_speed))  # Limit to 0.92-1.0
                    
                    compensation_map.append({
                        'chunk_start_idx': chunk_start,
                        'chunk_end_idx': index,
                        'video_speed': video_speed,
                        'compensation_time': overflow,
                        'chunk_start_time': chunk_start_time,
                        'chunk_end_time': chunk_end_time
                    })
                    
                    rprint(f"[cyan]🎬 Chunk {chunk_start}-{index} marked for video compensation: speed={video_speed:.3f}, time={overflow:.3f}s[/cyan]")
                else:
                    rprint(f"[green]✅ Chunk {chunk_start} to {index} gap compression resolved overflow[/green]")
            
            emoji = "⚡" if actual_speed <= accept else "🎯"
            rprint(f"[cyan]{emoji} Processed chunk {chunk_start} to {index} with voice speed {actual_speed:.2f}x[/cyan]")
            
            chunk_start = index + 1
    
    # Save compensation map for video processing
    if compensation_map:
        import json
        with open('output/audio/video_compensation.json', 'w', encoding='utf-8') as f:
            json.dump(compensation_map, f, indent=2)
        rprint(f"[bold yellow]📝 Saved {len(compensation_map)} video compensation requests[/bold yellow]")
    
    rprint("[bold green]✅ Audio chunks processing completed![/bold green]")
    return tasks_df

def gen_audio() -> None:
    """Main function: Generate audio and process timeline"""
    rprint("[bold magenta]🚀 Starting audio generation process...[/bold magenta]")
    
    # 🎯 Step1: Create necessary directories
    os.makedirs(_AUDIO_TMP_DIR, exist_ok=True)
    os.makedirs(_AUDIO_SEGS_DIR, exist_ok=True)
    
    # 📝 Step2: Load task file
    tasks_df = pd.read_excel(_8_1_AUDIO_TASK)
    rprint("[green]📊 Loaded task file successfully[/green]")
    
    # 🔊 Step3: Generate TTS audio
    tasks_df = generate_tts_audio(tasks_df)
    
    # 🔄 Step4: Merge audio chunks
    tasks_df = merge_chunks(tasks_df)
    
    # 💾 Step5: Save results
    tasks_df.to_excel(_8_1_AUDIO_TASK, index=False)
    rprint("[bold green]🎉 Audio generation completed successfully![/bold green]")

if __name__ == "__main__":
    gen_audio()
