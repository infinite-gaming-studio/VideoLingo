"""
WhisperX Cloud API Client for VideoLingo
Integrates with VideoLingo to use remote WhisperX service

Usage:
1. Deploy WhisperX on Colab/Kaggle using WhisperX_Cloud_Unified.ipynb
2. Set the WHISPERX_CLOUD_URL in config.yaml
3. VideoLingo will automatically use the cloud service
"""

import os
import sys
import requests
import tempfile
import time
from typing import Optional, Dict, Any, List
from rich import print as rprint

# Try to import VideoLingo utils
try:
    from core.utils import load_key
except ImportError:
    # Fallback when running standalone
    def load_key(key: str, default=None):
        """Fallback load_key function"""
        keys = key.split('.')
        value = _CONFIG
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    _CONFIG = {}

# API Configuration
DEFAULT_TIMEOUT = 300  # 5 minutes timeout for transcription
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def get_cloud_url() -> str:
    """Get cloud URL from various sources"""
    # Priority: environment variable > config.yaml
    url = os.getenv("WHISPERX_CLOUD_URL", "")
    if url:
        return url.rstrip('/')
    
    try:
        url = load_key("whisper.whisperX_cloud_url", "")
        if url:
            return url.rstrip('/')
    except:
        pass
    
    return ""


def check_cloud_connection(url: str = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Check if cloud WhisperX service is available
    
    Returns:
        Dict with 'available' (bool) and server info
    """
    url = url or get_cloud_url()
    if not url:
        return {'available': False, 'error': 'No cloud URL configured'}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(f"{url}/", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                rprint(f"[green]✅ Cloud WhisperX connected:[/green] {url}")
                rprint(f"[cyan]Platform:[/cyan] {data.get('platform', 'unknown')}")
                rprint(f"[cyan]Device:[/cyan] {data.get('device', 'unknown')}")
                if data.get('gpu_memory_gb'):
                    rprint(f"[cyan]GPU Memory:[/cyan] {data['gpu_memory_gb']:.2f} GB")
                return {'available': True, **data}
            else:
                return {'available': False, 'error': f'Status {response.status_code}'}
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                rprint(f"[yellow]⚠️ Connection timeout, retrying... ({attempt + 1}/{MAX_RETRIES})[/yellow]")
                time.sleep(RETRY_DELAY)
            else:
                return {'available': False, 'error': 'Connection timeout'}
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                rprint(f"[yellow]⚠️ Connection error, retrying... ({attempt + 1}/{MAX_RETRIES})[/yellow]")
                time.sleep(RETRY_DELAY)
            else:
                return {'available': False, 'error': str(e)}
    
    return {'available': False, 'error': 'Max retries exceeded'}


def transcribe_audio_cloud(
    raw_audio_file: str,
    vocal_audio_file: str,
    start: float,
    end: float,
    cloud_url: str = None,
    language: str = None,
    model: str = "large-v3",
    align: bool = True,
    speaker_diarization: bool = False,
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Transcribe audio segment using cloud WhisperX API
    
    Args:
        raw_audio_file: Path to original audio file
        vocal_audio_file: Path to vocal-separated audio
        start: Start time in seconds
        end: End time in seconds
        cloud_url: Cloud API URL (overrides config)
        language: Language code (e.g., 'en', 'zh')
        model: Model name (default: large-v3)
        align: Enable word-level alignment
        speaker_diarization: Enable speaker diarization
        timeout: Request timeout in seconds
    
    Returns:
        Dictionary with segments and word-level timestamps
    """
    url = cloud_url or get_cloud_url()
    
    if not url:
        raise ValueError("No cloud URL configured. Set whisper.whisperX_cloud_url in config.yaml or WHISPERX_CLOUD_URL env var")
    
    # Use vocal audio for better quality
    audio_file = vocal_audio_file if os.path.exists(vocal_audio_file) else raw_audio_file
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    rprint(f"[green]🚀 Sending to cloud WhisperX:[/green] {url}")
    rprint(f"[cyan]⏱️ Segment:[/cyan] {start:.2f}s - {end:.2f}s")
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # Prepare the audio file
            with open(audio_file, 'rb') as f:
                files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
                data = {
                    'language': language if language else '',
                    'model': model,
                    'align': str(align).lower(),
                    'speaker_diarization': str(speaker_diarization).lower()
                }
                
                # Make request
                response = requests.post(
                    f"{url}/transcribe",
                    files=files,
                    data=data,
                    timeout=timeout
                )
                
                if response.status_code != 200:
                    error_msg = response.text
                    raise Exception(f"API Error {response.status_code}: {error_msg}")
                
                result = response.json()
                
                if not result.get('success'):
                    raise Exception(f"Transcription failed: {result}")
                
                # Adjust timestamps back to original
                segments = result.get('segments', [])
                for segment in segments:
                    segment['start'] += start
                    segment['end'] += start
                    if 'words' in segment:
                        for word in segment['words']:
                            if 'start' in word:
                                word['start'] += start
                            if 'end' in word:
                                word['end'] += start
                
                rprint(f"[green]✅ Transcription complete![/green]")
                rprint(f"[cyan]Language:[/cyan] {result.get('language', 'unknown')}")
                rprint(f"[cyan]Processing time:[/cyan] {result.get('processing_time', 0):.2f}s")
                rprint(f"[cyan]Device:[/cyan] {result.get('device', 'unknown')}")
                rprint(f"[cyan]Platform:[/cyan] {result.get('platform', 'unknown')}")
                
                return {
                    'language': result.get('language', 'en'),
                    'segments': segments
                }
                
        except requests.exceptions.Timeout:
            last_error = f"Cloud API timeout after {timeout}s"
            rprint(f"[yellow]⚠️ Attempt {attempt + 1}/{MAX_RETRIES} timed out[/yellow]")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            last_error = f"Cannot connect to cloud API at {url}"
            rprint(f"[yellow]⚠️ Attempt {attempt + 1}/{MAX_RETRIES} connection failed[/yellow]")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            last_error = str(e)
            rprint(f"[yellow]⚠️ Attempt {attempt + 1}/{MAX_RETRIES} failed: {last_error}[/yellow]")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    raise Exception(f"Cloud transcription failed after {MAX_RETRIES} attempts: {last_error}")


class WhisperXCloudClient:
    """
    Client for WhisperX Cloud API
    Provides a convenient interface for interacting with the cloud service
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = (base_url or get_cloud_url()).rstrip('/')
        if not self.base_url:
            raise ValueError("Cloud URL not configured. Set WHISPERX_CLOUD_URL environment variable or provide base_url")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
    
    def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        response = self.session.get(f"{self.base_url}/", timeout=10)
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        response = self.session.get(f"{self.base_url}/stats", timeout=10)
        response.raise_for_status()
        return response.json()
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        model: str = "large-v3",
        align: bool = True,
        speaker_diarization: bool = False,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Transcribe audio file
        
        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'en', 'zh')
            model: Whisper model name
            align: Enable word-level alignment
            speaker_diarization: Enable speaker diarization
            timeout: Request timeout in seconds
        """
        with open(audio_path, 'rb') as f:
            files = {'audio': (os.path.basename(audio_path), f, 'audio/wav')}
            data = {
                'language': language if language else '',
                'model': model,
                'align': str(align).lower(),
                'speaker_diarization': str(speaker_diarization).lower()
            }
            
            response = self.session.post(
                f"{self.base_url}/transcribe",
                files=files,
                data=data,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear model cache on server to free GPU memory"""
        response = self.session.delete(f"{self.base_url}/cache", timeout=10)
        response.raise_for_status()
        return response.json()
    
    def is_available(self) -> bool:
        """Check if server is available"""
        try:
            self.health_check()
            return True
        except:
            return False


# Integration with VideoLingo's ASR module
def transcribe_audio_cloud_compatible(
    raw_audio_file: str,
    vocal_audio_file: str,
    start: float,
    end: float
) -> Dict[str, Any]:
    """
    Compatible function signature for VideoLingo integration
    Matches the signature of whisperX_local.transcribe_audio
    
    This function automatically reads configuration from VideoLingo's config.yaml
    """
    # Get config from VideoLingo
    try:
        whisper_language = load_key("whisper.language", "en")
        cloud_url = load_key("whisper.whisperX_cloud_url", "")
        model = load_key("whisper.model", "large-v3")
    except Exception as e:
        # Fallback to defaults
        whisper_language = "en"
        cloud_url = get_cloud_url()
        model = "large-v3"
    
    if not cloud_url:
        raise ValueError(
            "whisper.whisperX_cloud_url not configured in config.yaml.\n"
            "Please deploy WhisperX Cloud using whisperx_cloud/WhisperX_Cloud.ipynb "
            "and set the URL in config.yaml:\n"
            "  whisper:\n"
            "    runtime: 'cloud'\n"
            "    whisperX_cloud_url: 'YOUR_NGROK_URL'"
        )
    
    return transcribe_audio_cloud(
        raw_audio_file=raw_audio_file,
        vocal_audio_file=vocal_audio_file,
        start=start,
        end=end,
        cloud_url=cloud_url,
        language=whisper_language if whisper_language != 'auto' else None,
        model=model
    )


def get_server_info(url: str = None) -> Dict[str, Any]:
    """Get detailed information about the cloud server"""
    client = WhisperXCloudClient(url)
    try:
        health = client.health_check()
        stats = client.get_stats()
        return {
            'available': True,
            'health': health,
            'stats': stats
        }
    except Exception as e:
        return {
            'available': False,
            'error': str(e)
        }


# Usage example
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='WhisperX Cloud Client')
    parser.add_argument('--url', help='Cloud API URL')
    parser.add_argument('--check', action='store_true', help='Check connection')
    parser.add_argument('--stats', action='store_true', help='Get server stats')
    parser.add_argument('--transcribe', help='Transcribe audio file')
    parser.add_argument('--language', default=None, help='Language code')
    parser.add_argument('--model', default='large-v3', help='Model name')
    
    args = parser.parse_args()
    
    # Get URL
    url = args.url or get_cloud_url()
    
    if not url:
        print("❌ No cloud URL configured!")
        print("\nTo configure:")
        print("1. Deploy WhisperX Cloud using WhisperX_Cloud_Unified.ipynb")
        print("2. Set WHISPERX_CLOUD_URL environment variable, or")
        print("3. Update config.yaml with whisper.whisperX_cloud_url")
        sys.exit(1)
    
    print(f"Using cloud URL: {url}\n")
    
    if args.check:
        result = check_cloud_connection(url)
        if result['available']:
            print("✅ Server is available!")
            print(f"   Platform: {result.get('platform', 'unknown')}")
            print(f"   Device: {result.get('device', 'unknown')}")
        else:
            print(f"❌ Server unavailable: {result.get('error')}")
    
    elif args.stats:
        client = WhisperXCloudClient(url)
        try:
            stats = client.get_stats()
            print("📊 Server Statistics:")
            print(f"   Platform: {stats.get('platform')}")
            print(f"   Device: {stats.get('device')}")
            print(f"   Models Cached: {stats.get('models_cached', 0)}")
            if stats.get('gpu'):
                gpu = stats['gpu']
                print(f"   GPU: {gpu.get('name')}")
                print(f"   GPU Memory: {gpu.get('allocated_memory_gb', 0):.2f} / {gpu.get('total_memory_gb', 0):.2f} GB")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    elif args.transcribe:
        if not os.path.exists(args.transcribe):
            print(f"❌ File not found: {args.transcribe}")
            sys.exit(1)
        
        client = WhisperXCloudClient(url)
        try:
            print(f"🎯 Transcribing: {args.transcribe}")
            result = client.transcribe(
                audio_path=args.transcribe,
                language=args.language,
                model=args.model
            )
            print(f"\n✅ Success!")
            print(f"   Language: {result.get('language')}")
            print(f"   Segments: {len(result.get('segments', []))}")
            print(f"   Processing Time: {result.get('processing_time', 0):.2f}s")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    else:
        # Default: check connection
        result = check_cloud_connection(url)
        if result['available']:
            print("\n✅ Cloud WhisperX is ready!")
            print("\nTo transcribe audio:")
            print(f"  python {__file__} --transcribe audio.wav --language en")
        else:
            print(f"\n❌ Failed to connect to cloud WhisperX: {result.get('error')}")
            print("\nTo deploy:")
            print("1. Open whisperx_cloud/WhisperX_Cloud_Unified.ipynb in Google Colab or Kaggle")
            print("2. Run all cells and copy the ngrok URL")
            print("3. Set WHISPERX_CLOUD_URL environment variable or update config.yaml")
