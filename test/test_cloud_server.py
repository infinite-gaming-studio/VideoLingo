"""
VideoLingo Cloud Server Test Script
Tests both WhisperX ASR and Demucs Vocal Separation services
"""

import os
import sys
import requests
import tempfile
import base64
import time
import subprocess
import json
from pathlib import Path
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

# Configuration
CLOUD_URL = "https://adiaphoristic-zaire-reminiscently.ngrok-free.dev"
VIDEO_FILE = "../demo/bilibili_BV1FZ4y1i78V_852x480.mp4"
TIMEOUT = 300

# Check for GPU support
import shutil
def check_ffmpeg_gpu():
    """Check if ffmpeg supports hardware acceleration"""
    try:
        result = subprocess.run(['ffmpeg', '-hwaccels'], capture_output=True, text=True)
        hwaccels = result.stdout.strip()
        return hwaccels
    except:
        return ""

GPU_AVAILABLE = check_ffmpeg_gpu()
if GPU_AVAILABLE:
    rprint(f"[green]🚀 GPU acceleration available:[/green] {GPU_AVAILABLE}")
    # Use CUDA if available
    if 'cuda' in GPU_AVAILABLE.lower():
        USE_CUDA = True
    else:
        USE_CUDA = False
else:
    rprint("[yellow]⚠️ No GPU acceleration detected, using CPU[/yellow]")
    USE_CUDA = False


def extract_audio_from_video(video_path: str, output_path: str) -> bool:
    """Extract audio from video file using ffmpeg"""
    rprint(f"[yellow]📹 Extracting audio from video:[/yellow] {video_path}")

    try:
        cmd = [
            'ffmpeg',
        ]

        # Add GPU acceleration if available
        if USE_CUDA:
            cmd.extend(['-hwaccel', 'cuda'])

        cmd.extend([
            '-i', video_path,
            '-vn', '-acodec', 'libmp3lame', '-ab', '128k',
            '-ar', '44100', '-ac', '2',  # Use stereo (2 channels) and 44.1kHz for Demucs
            '-y', output_path
        ])

        if USE_CUDA:
            rprint("[cyan]🎮 Using CUDA acceleration for audio extraction[/cyan]")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            rprint(f"[green]✅ Audio extracted:[/green] {output_path}")
            return True
        else:
            rprint(f"[red]❌ Failed to extract audio:[/red] {result.stderr}")
            return False
    except Exception as e:
        rprint(f"[red]❌ Error extracting audio:[/red] {str(e)}")
        return False


def test_health_check() -> bool:
    """Test server health endpoint"""
    rprint("\n" + "=" * 60)
    rprint("[bold cyan]🏥 Testing Health Check Endpoint[/bold cyan]")
    rprint("=" * 60)

    try:
        response = requests.get(f"{CLOUD_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()

            # Create table for health check
            table = Table(title="Server Health Status")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Status", data.get('status', 'unknown'))
            table.add_row("Device", data.get('device', 'unknown'))
            table.add_row("Platform", data.get('platform', 'unknown'))
            table.add_row("CUDA Available", str(data.get('cuda_available', False)))
            table.add_row("GPU Memory", f"{data.get('gpu_memory', 0):.2f} GB")
            table.add_row("Server Version", data.get('server_version', 'unknown'))

            rprint(table)

            # Check services
            services = data.get('services', {})
            rprint("\n[bold]Services:[/bold]")
            for svc_name, svc_info in services.items():
                status = "[green]✅ Available[/green]" if svc_info.get('available') else "[red]❌ Unavailable[/red]"
                rprint(f"  {status} {svc_name}: {svc_info.get('endpoint', '')}")

            return data.get('status') == 'healthy'
        else:
            rprint(f"[red]❌ Health check failed with status code:[/red] {response.status_code}")
            return False
    except Exception as e:
        rprint(f"[red]❌ Health check error:[/red] {str(e)}")
        return False


def test_asr_service(audio_file: str, output_dir: Path) -> bool:
    """Test WhisperX ASR service"""
    rprint("\n" + "=" * 60)
    rprint("[bold cyan]🎤 Testing WhisperX ASR Service[/bold cyan]")
    rprint("=" * 60)

    if not os.path.exists(audio_file):
        rprint(f"[red]❌ Audio file not found:[/red] {audio_file}")
        return False

    try:
        rprint(f"[yellow]📤 Uploading audio to:[/yellow] {CLOUD_URL}/asr/transcribe")

        with open(audio_file, 'rb') as f:
            files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
            data = {
                'model': 'large-v3',
                'align': 'true',
                'speaker_diarization': 'false'
            }

            start_time = time.time()
            response = requests.post(
                f"{CLOUD_URL}/asr/transcribe",
                files=files,
                data=data,
                timeout=TIMEOUT
            )
            total_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()

            if result.get('success'):
                rprint(f"[green]✅ ASR Transcription Successful![/green]")

                # Create summary table
                table = Table(title="Transcription Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Language", result.get('language', 'unknown'))
                table.add_row("Processing Time", f"{result.get('processing_time', 0):.2f}s")
                table.add_row("Total Time", f"{total_time:.2f}s")
                table.add_row("Segments", str(len(result.get('segments', []))))
                table.add_row("Device", result.get('device', 'unknown'))
                table.add_row("Model", result.get('model', 'unknown'))

                rprint(table)

                # Display some segments
                segments = result.get('segments', [])
                if segments:
                    rprint("\n[bold]First 5 Transcription Segments:[/bold]")
                    for i, seg in enumerate(segments[:5]):
                        text = seg.get('text', '').strip()
                        start = seg.get('start', 0)
                        end = seg.get('end', 0)
                        rprint(f"  [{start:.2f}s - {end:.2f}s] {text}")

                    if len(segments) > 5:
                        rprint(f"  ... and {len(segments) - 5} more segments")

                # Save transcription result to file
                result_path = output_dir / "asr_transcription.json"
                with open(result_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                rprint(f"[green]✅ Transcription saved to:[/green] {result_path}")

                return True
            else:
                rprint(f"[red]❌ Transcription failed:[/red] {result}")
                return False
        else:
            rprint(f"[red]❌ API Error {response.status_code}:[/red] {response.text}")
            return False

    except requests.exceptions.Timeout:
        rprint(f"[red]❌ Request timed out after {TIMEOUT}s[/red]")
        return False
    except Exception as e:
        rprint(f"[red]❌ ASR test error:[/red] {str(e)}")
        return False


def test_separation_service(audio_file: str, output_dir: Path) -> bool:
    """Test Demucs Vocal Separation service"""
    rprint("\n" + "=" * 60)
    rprint("[bold cyan]🎵 Testing Demucs Vocal Separation Service[/bold cyan]")
    rprint("=" * 60)

    if not os.path.exists(audio_file):
        rprint(f"[red]❌ Audio file not found:[/red] {audio_file}")
        return False

    try:
        rprint(f"[yellow]📤 Uploading audio to:[/yellow] {CLOUD_URL}/separation/separate")

        with open(audio_file, 'rb') as f:
            files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
            data = {'return_files': 'true'}

            start_time = time.time()
            response = requests.post(
                f"{CLOUD_URL}/separation/separate",
                files=files,
                data=data,
                timeout=TIMEOUT
            )
            total_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()

            if result.get('success'):
                rprint(f"[green]✅ Vocal Separation Successful![/green]")

                # Create summary table
                table = Table(title="Separation Summary")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Processing Time", f"{result.get('processing_time', 0):.2f}s")
                table.add_row("Total Time", f"{total_time:.2f}s")
                table.add_row("Device", result.get('device', 'unknown'))
                table.add_row("Vocals Size", f"{len(result.get('vocals_base64', '')) // 1024} KB" if result.get('vocals_base64') else "N/A")
                table.add_row("Background Size", f"{len(result.get('background_base64', '')) // 1024} KB" if result.get('background_base64') else "N/A")

                rprint(table)

                # Save output files
                vocals_b64 = result.get('vocals_base64')
                background_b64 = result.get('background_base64')

                if vocals_b64:
                    vocals_path = output_dir / "separation_vocals.mp3"
                    with open(vocals_path, 'wb') as f:
                        f.write(base64.b64decode(vocals_b64))
                    rprint(f"[green]✅ Vocals saved to:[/green] {vocals_path}")

                if background_b64:
                    bg_path = output_dir / "separation_background.mp3"
                    with open(bg_path, 'wb') as f:
                        f.write(base64.b64decode(background_b64))
                    rprint(f"[green]✅ Background saved to:[/green] {bg_path}")

                return True
            else:
                rprint(f"[red]❌ Separation failed:[/red] {result}")
                return False
        else:
            rprint(f"[red]❌ API Error {response.status_code}:[/red] {response.text}")
            return False

    except requests.exceptions.Timeout:
        rprint(f"[red]❌ Request timed out after {TIMEOUT}s[/red]")
        return False
    except Exception as e:
        rprint(f"[red]❌ Separation test error:[/red] {str(e)}")
        return False


def main():
    """Main test function"""
    rprint(Panel.fit("[bold green]VideoLingo Cloud Server Test[/bold green]\n" +
                     f"Server: {CLOUD_URL}\n" +
                     f"Video: {VIDEO_FILE}",
                     title="Test Configuration"))

    # Check if video file exists
    if not os.path.exists(VIDEO_FILE):
        rprint(f"[red]❌ Video file not found:[/red] {VIDEO_FILE}")
        rprint(f"[yellow]Please ensure the file exists in the project root directory[/yellow]")
        return

    # Extract audio from video
    output_dir = Path("../demo/test_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = output_dir / "test_audio.wav"

    if not extract_audio_from_video(VIDEO_FILE, str(audio_file)):
        rprint("[red]❌ Failed to extract audio, skipping tests[/red]")
        return

    # Run tests
    results = {}

    # Test 1: Health Check
    results['health_check'] = test_health_check()

    # Test 2: ASR Service
    results['asr'] = test_asr_service(str(audio_file), output_dir)

    # Test 3: Separation Service
    results['separation'] = test_separation_service(str(audio_file), output_dir)

    # Summary
    rprint("\n" + "=" * 60)
    rprint("[bold cyan]📊 Test Summary[/bold cyan]")
    rprint("=" * 60)

    for test_name, passed in results.items():
        status = "[green]✅ PASSED[/green]" if passed else "[red]❌ FAILED[/red]"
        rprint(f"{status} {test_name.replace('_', ' ').title()}")

    all_passed = all(results.values())
    rprint("\n" + ("=" * 60))
    if all_passed:
        rprint("[bold green]🎉 All tests passed![/bold green]")
    else:
        rprint("[bold red]⚠️ Some tests failed![/bold red]")
    rprint("=" * 60)

    rprint(f"\n[cyan]📁 All test outputs saved to:[/cyan] {output_dir}")
    rprint(f"[cyan]  - test_audio.wav (extracted audio)[/cyan]")
    rprint(f"[cyan]  - asr_transcription.json (ASR result)[/cyan]")
    rprint(f"[cyan]  - separation_vocals.mp3 (vocals)[/cyan]")
    rprint(f"[cyan]  - separation_background.mp3 (background)[/cyan]")


if __name__ == "__main__":
    main()
