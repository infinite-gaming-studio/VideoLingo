"""
VideoLingo Unified Cloud API Client
Supports both WhisperX ASR and Demucs Vocal Separation

Usage:
1. Deploy unified server using Unified_Cloud_Server.ipynb
2. Set the CLOUD_URL in config.yaml
3. VideoLingo will automatically use the cloud service
"""

import os
import sys
import requests
import tempfile
import time
import base64
from typing import Optional, Dict, Any
from rich import print as rprint

# Try to import VideoLingo utils
try:
    from core.utils import load_key
except ImportError:
    def load_key(key: str, default=None):
        return default

# API Configuration
DEFAULT_TIMEOUT = 600  # Increased from 300 to 600 seconds (10 minutes) for long audio files
MAX_RETRIES = 3
RETRY_DELAY = 5


def get_cloud_url() -> str:
    """Get cloud URL from environment or config
    Priority: CLOUD_URL env > cloud_native.cloud_url"""
    url = os.getenv("CLOUD_URL", "")
    if url:
        return url.rstrip('/')
    
    # Unified cloud_native configuration
    try:
        url = load_key("cloud_native.cloud_url", "")
        if url:
            return url.rstrip('/')
    except:
        pass
    
    return ""


def get_cloud_token() -> str:
    """Get cloud token from environment or config
    Priority: WHISPERX_CLOUD_TOKEN env > cloud_native.token"""
    token = os.getenv("WHISPERX_CLOUD_TOKEN", "")
    if token:
        return token
    
    # Unified cloud_native configuration
    try:
        token = load_key("cloud_native.token", "")
        if token:
            return token
    except:
        pass
    
    return ""


def check_cloud_connection(url: str = None, timeout: int = 10) -> Dict[str, Any]:
    """Check if cloud service is available"""
    url = url or get_cloud_url()
    if not url:
        return {'available': False, 'error': 'No cloud URL configured'}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(f"{url}/", timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                rprint(f"[green]✅ Cloud service connected:[/green] {url}")
                rprint(f"[cyan]Platform:[/cyan] {data.get('platform', 'unknown')}")
                rprint(f"[cyan]Device:[/cyan] {data.get('device', 'unknown')}")
                services = data.get('services', {})
                for svc_name, svc_info in services.items():
                    status = "✅" if svc_info.get('available') else "❌"
                    rprint(f"  {status} {svc_name}: {svc_info.get('endpoint', '')}")
                return {'available': True, **data}
            else:
                return {'available': False, 'error': f'Status {response.status_code}'}
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                rprint(f"[yellow]⚠️ Timeout, retrying... ({attempt + 1}/{MAX_RETRIES})[/yellow]")
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
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    timeout: int = None,  # Will use config or dynamic timeout based on audio length
    token: str = None
) -> Dict[str, Any]:
    """Transcribe audio using cloud ASR service"""
    url = cloud_url or get_cloud_url()
    
    # Get timeout from config if not provided
    if timeout is None:
        try:
            timeout = load_key("cloud_native.timeout", None)
        except:
            pass
    
    # Calculate dynamic timeout based on audio segment length
    # WhisperX typically needs ~1-2x real-time, diarization adds more time
    segment_duration = end - start
    if timeout is None:
        if speaker_diarization:
            # Diarization takes longer, especially for long audio
            timeout = max(DEFAULT_TIMEOUT, int(segment_duration * 2.5))
        else:
            timeout = max(DEFAULT_TIMEOUT, int(segment_duration * 1.5))
    rprint(f"[dim]⏱️ Timeout: {timeout}s for {segment_duration:.1f}s audio segment[/dim]")

    if not url:
        raise ValueError("No cloud URL configured")

    audio_file = vocal_audio_file if os.path.exists(vocal_audio_file) else raw_audio_file

    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    rprint(f"[cyan]⏱️ Segment:[/cyan] {start:.2f}s - {end:.2f}s")

    # auth headers
    headers = {}
    if not token:
        token = get_cloud_token()
    if token:
        headers['Authorization'] = f"Bearer {token}"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with open(audio_file, 'rb') as f:
                files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
                data = {
                    'language': language if language else '',
                    'model': model,
                    'align': str(align).lower(),
                    'speaker_diarization': str(speaker_diarization).lower()
                }
                if min_speakers not in [None, '', 0]:
                    data['min_speakers'] = min_speakers
                if max_speakers not in [None, '', 0]:
                    data['max_speakers'] = max_speakers

                # 📝 Print request details
                rprint(f"[dim]📤 Request to: {url}/asr/transcribe[/dim]")
                rprint(f"[dim]   Params: {data}[/dim]")

                response = requests.post(
                    f"{url}/asr/transcribe",
                    files=files,
                    data=data,
                    timeout=timeout,
                    headers=headers
                )

                if response.status_code != 200:
                    error_msg = response.text
                    raise Exception(f"API Error {response.status_code}: {error_msg}")

                result = response.json()

                if not result.get('success'):
                    raise Exception(f"Transcription failed: {result}")

                # 📝 Print raw response details
                rprint(f"[dim]📥 Response received:[/dim]")
                rprint(f"[dim]   Keys: {list(result.keys())}[/dim]")
                rprint(f"[dim]   Speakers in response: {result.get('speakers', 'N/A')}[/dim]")

                # Adjust timestamps
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

                # Debug: Check for speaker info in response
                speakers_found = list(set(s.get('speaker') for s in segments if 'speaker' in s))
                rprint(f"[blue]🔍 First segment speaker:[/blue] {segments[0].get('speaker') if segments else 'N/A'}")
                rprint(f"[blue]🔍 Speakers found:[/blue] {speakers_found if speakers_found else 'None'}")

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


def separate_audio_cloud(
    audio_file: str,
    vocals_output: str,
    background_output: str,
    cloud_url: str = None,
    timeout: int = None,  # Will use dynamic timeout based on audio length
    token: str = None
) -> bool:
    """Separate audio using cloud separation service"""
    url = cloud_url or get_cloud_url()
    
    if not url:
        raise ValueError("No cloud URL configured")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    # Calculate dynamic timeout based on audio file duration
    # Demucs typically needs ~0.5-1x real-time
    try:
        import subprocess
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
               '-of', 'default=noprint_wrappers=1:nokey=1', audio_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        if timeout is None:
            timeout = max(DEFAULT_TIMEOUT, int(duration * 1.5))
            rprint(f"[dim]⏱️ Calculated timeout: {timeout}s for {duration:.1f}s audio[/dim]")
    except Exception:
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
    
    rprint(f"[cyan]Input:[/cyan] {audio_file}")
    
    # auth headers
    headers = {}
    if not token:
        token = get_cloud_token()
    if token:
        headers['Authorization'] = f"Bearer {token}"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with open(audio_file, 'rb') as f:
                files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
                data = {'return_files': 'true'}
                
                response = requests.post(
                    f"{url}/separation/separate",
                    files=files,
                    data=data,
                    timeout=timeout,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_msg = response.text
                    raise Exception(f"API Error {response.status_code}: {error_msg}")
                
                result = response.json()
                
                if not result.get('success'):
                    raise Exception(f"Separation failed: {result}")
                
                # Decode and save vocals
                vocals_b64 = result.get('vocals_base64')
                if vocals_b64:
                    os.makedirs(os.path.dirname(vocals_output) or '.', exist_ok=True)
                    with open(vocals_output, 'wb') as f:
                        f.write(base64.b64decode(vocals_b64))
                    rprint(f"[green]✅ Vocals saved:[/green] {vocals_output}")
                
                # Decode and save background
                background_b64 = result.get('background_base64')
                if background_b64:
                    os.makedirs(os.path.dirname(background_output) or '.', exist_ok=True)
                    with open(background_output, 'wb') as f:
                        f.write(base64.b64decode(background_b64))
                    rprint(f"[green]✅ Background saved:[/green] {background_output}")
                
                rprint(f"[cyan]Processing time:[/cyan] {result.get('processing_time', 0):.2f}s")
                
                return True
                
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
    
    raise Exception(f"Cloud separation failed after {MAX_RETRIES} attempts: {last_error}")


class UnifiedCloudClient:
    """Unified client for VideoLingo Cloud API"""
    
    def __init__(self, base_url: str = None, token: str = None):
        self.base_url = (base_url or get_cloud_url()).rstrip('/')
        if not self.base_url:
            raise ValueError("Cloud URL not configured")
        
        self.session = requests.Session()
        headers = {'Accept': 'application/json'}

        # Get token
        if not token:
            token = get_cloud_token()
        
        if token:
            headers['Authorization'] = f"Bearer {token}"
            
        self.session.headers.update(headers)
    
    def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        response = self.session.get(f"{self.base_url}/", timeout=10)
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
        """Transcribe audio file"""
        with open(audio_path, 'rb') as f:
            files = {'audio': (os.path.basename(audio_path), f, 'audio/wav')}
            data = {
                'language': language if language else '',
                'model': model,
                'align': str(align).lower(),
                'speaker_diarization': str(speaker_diarization).lower()
            }
            
            response = self.session.post(
                f"{self.base_url}/asr/transcribe",
                files=files,
                data=data,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
    
    def separate(
        self,
        audio_path: str,
        vocals_output: str,
        background_output: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> bool:
        """Separate audio file"""
        return separate_audio_cloud(
            audio_file=audio_path,
            vocals_output=vocals_output,
            background_output=background_output,
            cloud_url=self.base_url,
            timeout=timeout,
            token=self.session.headers.get('Authorization', '').replace('Bearer ', '') if 'Authorization' in self.session.headers else None
        )
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear model cache on server"""
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


# Integration functions for VideoLingo
def transcribe_audio_cloud_compatible(
    raw_audio_file: str,
    vocal_audio_file: str,
    start: float,
    end: float
) -> Dict[str, Any]:
    """Compatible function for VideoLingo ASR integration"""
    try:
        whisper_language = load_key("whisper.language", "en")
        model = load_key("whisper.model", "large-v3")
        diarization = load_key("whisper.diarization", False)
        min_speakers = load_key("whisper.min_speakers", None)
        max_speakers = load_key("whisper.max_speakers", None)
    except:
        whisper_language = "en"
        model = "large-v3"
        diarization = False
        min_speakers = None
        max_speakers = None
    
    # Use unified cloud configuration
    cloud_url = get_cloud_url()
    token = get_cloud_token()
    
    if not cloud_url:
        raise ValueError(
            "Cloud URL not configured. Set cloud_native.cloud_url in config.yaml\n"
            "or set CLOUD_URL environment variable."
        )
    
    return transcribe_audio_cloud(
        raw_audio_file=raw_audio_file,
        vocal_audio_file=vocal_audio_file,
        start=start,
        end=end,
        cloud_url=cloud_url,
        language=whisper_language if whisper_language != 'auto' else None,
        model=model,
        speaker_diarization=diarization,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        token=token
    )


def separate_audio_cloud_compatible(
    raw_audio_file: str,
    vocals_output: str,
    background_output: str
) -> bool:
    """Compatible function for VideoLingo separation integration"""
    # Use unified cloud configuration (same as ASR)
    cloud_url = get_cloud_url()
    token = get_cloud_token()
    
    if not cloud_url:
        raise ValueError(
            "Cloud URL not configured. Set cloud_native.cloud_url in config.yaml\n"
            "or set CLOUD_URL environment variable."
        )
    
    return separate_audio_cloud(
        audio_file=raw_audio_file,
        vocals_output=vocals_output,
        background_output=background_output,
        cloud_url=cloud_url,
        token=token
    )


def get_server_info(url: str = None) -> Dict[str, Any]:
    """Get detailed information about the cloud server"""
    client = UnifiedCloudClient(url)
    try:
        health = client.health_check()
        return {
            'available': True,
            'health': health
        }
    except Exception as e:
        return {
            'available': False,
            'error': str(e)
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='VideoLingo Unified Cloud Client')
    parser.add_argument('--url', help='Cloud API URL')
    parser.add_argument('--check', action='store_true', help='Check connection')
    parser.add_argument('--transcribe', help='Transcribe audio file')
    parser.add_argument('--separate', help='Separate audio file')
    parser.add_argument('--vocals', help='Vocals output path (for separation)')
    parser.add_argument('--background', help='Background output path (for separation)')
    parser.add_argument('--language', default=None, help='Language code')
    
    args = parser.parse_args()
    
    url = args.url or get_cloud_url()
    
    if not url:
        print("❌ No cloud URL configured!")
        print("\nTo configure:")
        print("1. Deploy unified server using Unified_Cloud_Server.ipynb")
        print("2. Set CLOUD_URL environment variable or update config.yaml")
        sys.exit(1)
    
    print(f"Using cloud URL: {url}\n")
    
    if args.check:
        result = check_cloud_connection(url)
        if result['available']:
            print("\n✅ Server is available!")
        else:
            print(f"\n❌ Server unavailable: {result.get('error')}")
    
    elif args.transcribe:
        if not os.path.exists(args.transcribe):
            print(f"❌ File not found: {args.transcribe}")
            sys.exit(1)
        
        try:
            client = UnifiedCloudClient(url)
            result = client.transcribe(args.transcribe, language=args.language)
            print(f"\n✅ Transcription complete!")
            print(f"   Language: {result.get('language')}")
            print(f"   Segments: {len(result.get('segments', []))}")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    
    elif args.separate and args.vocals and args.background:
        if not os.path.exists(args.separate):
            print(f"❌ Input file not found: {args.separate}")
            sys.exit(1)
        
        try:
            separate_audio_cloud(
                audio_file=args.separate,
                vocals_output=args.vocals,
                background_output=args.background,
                cloud_url=url
            )
            print("\n✅ Separation complete!")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    
    else:
        result = check_cloud_connection(url)
        if result['available']:
            print("\n✅ VideoLingo Cloud is ready!")
            print("\nUsage:")
            print(f"  Transcribe: python {__file__} --transcribe audio.wav --language en")
            print(f"  Separate:   python {__file__} --separate audio.wav --vocals v.mp3 --background b.mp3")
        else:
            print(f"\n❌ Failed to connect: {result.get('error')}")
