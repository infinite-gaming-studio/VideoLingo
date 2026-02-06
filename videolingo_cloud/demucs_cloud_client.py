"""
Demucs Cloud API Client for VideoLingo
Integrates with VideoLingo to use remote Demucs vocal separation service

Usage:
1. Deploy Demucs on Colab/Kaggle using demucs_cloud_server.py
2. Set the DEMUCS_CLOUD_URL in config.yaml
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
    # Fallback when running standalone
    def load_key(key: str, default=None):
        """Fallback load_key function"""
        return default

# API Configuration
DEFAULT_TIMEOUT = 300  # 5 minutes timeout for separation
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def get_cloud_url() -> str:
    """Get cloud URL from various sources"""
    # Priority: environment variable > config.yaml
    url = os.getenv("DEMUCS_CLOUD_URL", "")
    if url:
        return url.rstrip('/')
    
    try:
        url = load_key("cloud_native.cloud_url", "")
        if not url:
            url = load_key("demucs_cloud_url", "")
        if not url:
            url = load_key("whisper.whisperX_cloud_url", "")
        if url:
            return url.rstrip('/')
    except:
        pass
    
    return ""


def check_cloud_connection(url: str = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Check if cloud Demucs service is available
    
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
                rprint(f"[green]✅ Cloud Demucs connected:[/green] {url}")
                rprint(f"[cyan]Platform:[/cyan] {data.get('platform', 'unknown')}")
                rprint(f"[cyan]Device:[/cyan] {data.get('device', 'unknown')}")
                if data.get('gpu_memory'):
                    rprint(f"[cyan]GPU Memory:[/cyan] {data['gpu_memory']:.2f} GB")
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


def separate_audio_cloud(
    audio_file: str,
    vocals_output: str,
    background_output: str,
    cloud_url: str = None,
    timeout: int = DEFAULT_TIMEOUT,
    token: str = None
) -> bool:
    """
    Separate audio using cloud Demucs API
    
    Args:
        audio_file: Path to input audio file
        vocals_output: Path to save vocals output
        background_output: Path to save background output
        cloud_url: Cloud API URL (overrides config)
        timeout: Request timeout in seconds
    
    Returns:
        True if successful, False otherwise
    """
    url = cloud_url or get_cloud_url()
    
    if not url:
        raise ValueError("No cloud URL configured. Set demucs_cloud_url in config.yaml or DEMUCS_CLOUD_URL env var")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    rprint(f"[cyan]Input:[/cyan] {audio_file}")
    
    # auth headers
    headers = {}
    if not token:
        token = os.getenv("WHISPERX_CLOUD_TOKEN")
        if not token:
            try:
                # Priority: demucs_token (if exists) > whisperX_token
                token = load_key("demucs_token", "")
                if not token:
                    token = load_key("whisper.whisperX_token", "")
            except:
                pass
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # Prepare the audio file
            with open(audio_file, 'rb') as f:
                files = {'audio': (os.path.basename(audio_file), f, 'audio/wav')}
                data = {'return_files': 'true'}
                
                # Make request
                response = requests.post(
                    f"{url}/separate",
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
                rprint(f"[cyan]Device:[/cyan] {result.get('device', 'unknown')}")
                
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


class DemucsCloudClient:
    """
    Client for Demucs Cloud API
    Provides a convenient interface for interacting with the cloud service
    """
    
    def __init__(self, base_url: str = None, token: str = None):
        self.base_url = (base_url or get_cloud_url()).rstrip('/')
        if not self.base_url:
            raise ValueError("Cloud URL not configured. Set DEMUCS_CLOUD_URL environment variable or provide base_url")
        
        self.session = requests.Session()
        headers = {'Accept': 'application/json'}

        # Get token
        if not token:
            token = os.getenv("VIDEOLINGO_CLOUD_TOKEN") or os.getenv("WHISPERX_CLOUD_TOKEN")
            if not token:
                try:
                    token = load_key("cloud_native.token", "")
                    if not token:
                        token = load_key("whisper.whisperX_token", "")
                except:
                    pass
        
        if token:
            headers['Authorization'] = f"Bearer {token}"
            
        self.session.headers.update(headers)
    
    def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        response = self.session.get(f"{self.base_url}/", timeout=10)
        response.raise_for_status()
        return response.json()
    
    def separate(
        self,
        audio_path: str,
        vocals_output: str,
        background_output: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> bool:
        """
        Separate audio file
        
        Args:
            audio_path: Path to audio file
            vocals_output: Path to save vocals
            background_output: Path to save background
            timeout: Request timeout in seconds
        """
        return separate_audio_cloud(
            audio_file=audio_path,
            vocals_output=vocals_output,
            background_output=background_output,
            cloud_url=self.base_url,
            timeout=timeout,
            token=self.session.headers.get('Authorization', '').replace('Bearer ', '') if 'Authorization' in self.session.headers else None
        )
    
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


# Integration with VideoLingo's demucs module
def separate_audio_cloud_compatible(
    raw_audio_file: str,
    vocals_output: str,
    background_output: str
) -> bool:
    """
    Compatible function signature for VideoLingo integration
    Matches the signature of demucs_vl.demucs_audio but with explicit paths
    
    This function automatically reads configuration from VideoLingo's config.yaml
    """
    # Get config from VideoLingo
    try:
        cloud_url = get_cloud_url()
        token = os.getenv("VIDEOLINGO_CLOUD_TOKEN") or os.getenv("WHISPERX_CLOUD_TOKEN")
        if not token:
            token = load_key("cloud_native.token", "")
            if not token:
                 token = load_key("whisper.whisperX_token", "")
    except Exception as e:
        cloud_url = get_cloud_url()
        token = None
    
    if not cloud_url:
        raise ValueError(
            "demucs_cloud_url not configured in config.yaml.\n"
            "Please deploy Demucs Cloud and set the URL in config.yaml:\n"
            "  demucs_cloud_url: 'YOUR_NGROK_URL'\n\n"
            "Or set DEMUCS_CLOUD_URL environment variable."
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
    client = DemucsCloudClient(url)
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


# Usage example
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Demucs Cloud Client')
    parser.add_argument('--url', help='Cloud API URL')
    parser.add_argument('--check', action='store_true', help='Check connection')
    parser.add_argument('--input', help='Input audio file')
    parser.add_argument('--vocals', help='Vocals output path')
    parser.add_argument('--background', help='Background output path')
    
    args = parser.parse_args()
    
    # Get URL
    url = args.url or get_cloud_url()
    
    if not url:
        print("❌ No cloud URL configured!")
        print("\nTo configure:")
        print("1. Deploy Demucs Cloud using demucs_server.py")
        print("2. Set DEMUCS_CLOUD_URL environment variable, or")
        print("3. Update config.yaml with demucs_cloud_url")
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
    
    elif args.input and args.vocals and args.background:
        if not os.path.exists(args.input):
            print(f"❌ Input file not found: {args.input}")
            sys.exit(1)
        
        try:
            print(f"🎯 Separating: {args.input}")
            separate_audio_cloud(
                audio_file=args.input,
                vocals_output=args.vocals,
                background_output=args.background,
                cloud_url=url
            )
            print("\n✅ Separation complete!")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    
    else:
        # Default: check connection
        result = check_cloud_connection(url)
        if result['available']:
            print("\n✅ Cloud Demucs is ready!")
            print("\nTo separate audio:")
            print(f"  python {__file__} --input audio.wav --vocals vocals.mp3 --background bg.mp3")
        else:
            print(f"\n❌ Failed to connect to cloud Demucs: {result.get('error')}")
            print("\nTo deploy:")
            print("1. Run demucs_server.py on a GPU server (Colab, Kaggle, etc.)")
            print("2. Copy the ngrok URL and set DEMUCS_CLOUD_URL")
