"""
VideoLingo Demucs Audio Separation Module
Supports cloud-native remote processing only.

Cloud Native Mode:
- When whisper.runtime='cloud' in config.yaml
- All separation processing is done via remote Demucs cloud service
- No local torch/demucs dependencies required
"""

import os
from rich.console import Console
from rich import print as rprint
from typing import Optional
from core.utils.models import *
from core.utils import vprint

console = Console()

# Cloud API configuration
DEMUCS_CLOUD_URL = os.getenv("DEMUCS_CLOUD_URL", "")


def is_cloud_native():
    """Check if cloud native mode is enabled in config
    Uses runtime='cloud'"""
    try:
        from core.utils import load_key
        # Cloud mode is enabled when runtime='cloud'
        if load_key("whisper.runtime", "") == "cloud":
            return True
        return False
    except:
        return False


def is_cloud_separation_enabled():
    """Check if cloud separation feature is enabled"""
    # Cloud separation is enabled when in cloud native mode
    return is_cloud_native()

def get_cloud_url() -> str:
    """Get cloud URL from environment or config
    Priority: DEMUCS_CLOUD_URL env > cloud_native.cloud_url"""
    if DEMUCS_CLOUD_URL:
        return DEMUCS_CLOUD_URL.rstrip('/')
    
    try:
        from core.utils import load_key
        # Unified cloud_native configuration (recommended)
        url = load_key("cloud_native.cloud_url", "")
        if url:
            return url.rstrip('/')
    except:
        pass
    
    return ""

def check_cloud_available(url: str = None) -> bool:
    """Check if cloud Demucs service is available"""
    url = url or get_cloud_url()
    if not url:
        return False
    
    try:
        import requests
        response = requests.get(f"{url}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            services = data.get('services', {})
            return services.get('separation', {}).get('available', False)
        return False
    except:
        return False

def separate_audio_cloud(cloud_url: str = None):
    """Cloud Demucs processing via unified API"""
    url = cloud_url or get_cloud_url()
    
    if not url:
        raise ValueError(
            "Cloud URL not configured. Set cloud_native.cloud_url in config.yaml "
            "or DEMUCS_CLOUD_URL env var"
        )
    
    # Get timeout from config
    timeout = None
    try:
        from core.utils import load_key
        timeout = load_key("cloud_native.timeout", None)
    except:
        pass
    
    try:
        # Try unified client first
        from videolingo_cloud.client import separate_audio_cloud as cloud_separate
        cloud_separate(
            audio_file=_RAW_AUDIO_FILE,
            vocals_output=_VOCAL_AUDIO_FILE,
            background_output=_BACKGROUND_AUDIO_FILE,
            cloud_url=url,
            timeout=timeout
        )
    except ImportError:
        # Fallback: inline implementation
        import requests
        import base64
        from core.utils import load_key
        
        vprint(f"🚀 Using cloud Demucs (fallback): {url}")
        vprint("🎵 Sending audio for separation...")
        
        # Get token from cloud_native or legacy key
        token = os.getenv("VIDEOLINGO_CLOUD_TOKEN") or os.getenv("WHISPERX_CLOUD_TOKEN")
        if not token:
            try:
                token = load_key("cloud_native.token", "")
                if not token:
                    token = load_key("whisper.whisperX_token", "")
            except:
                pass
        
        headers = {}
        if token:
            headers['Authorization'] = f"Bearer {token}"
            
        with open(_RAW_AUDIO_FILE, 'rb') as f:
            files = {'audio': (os.path.basename(_RAW_AUDIO_FILE), f, 'audio/wav')}
            data = {'return_files': 'true'}
            
            response = requests.post(
                f"{url}/separation/separate",
                files=files,
                data=data,
                timeout=300,
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"API Error {response.status_code}: {response.text}")
            
            result = response.json()
            
            if not result.get('success'):
                raise Exception(f"Separation failed: {result}")
            
            # Decode and save
            vocals_b64 = result.get('vocals_base64')
            if vocals_b64:
                os.makedirs(os.path.dirname(_VOCAL_AUDIO_FILE) or '.', exist_ok=True)
                with open(_VOCAL_AUDIO_FILE, 'wb') as f:
                    f.write(base64.b64decode(vocals_b64))
                vprint(f"[green]✅ Vocals saved[/green]")
            
            background_b64 = result.get('background_base64')
            if background_b64:
                os.makedirs(os.path.dirname(_BACKGROUND_AUDIO_FILE) or '.', exist_ok=True)
                with open(_BACKGROUND_AUDIO_FILE, 'wb') as f:
                    f.write(base64.b64decode(background_b64))
                vprint(f"[green]✅ Background saved[/green]")

def demucs_audio():
    """
    Main entry point for Demucs audio separation
    Supports Cloud Native Mode only
    """
    if os.path.exists(_VOCAL_AUDIO_FILE) and os.path.exists(_BACKGROUND_AUDIO_FILE):
        vprint(f"[yellow]⚠️ {_VOCAL_AUDIO_FILE} and {_BACKGROUND_AUDIO_FILE} already exist, skip Demucs processing.[/yellow]")
        return
    
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    
    cloud_url = get_cloud_url()
    
    if not cloud_url:
        raise ValueError(
            "Cloud Native Mode is enabled but no cloud URL is configured.\n"
            "Please set cloud_native.cloud_url in config.yaml"
        )
    
    if not check_cloud_available(cloud_url):
        raise ConnectionError(
            f"Cloud Native Mode is enabled but cloud Demucs service is not available at {cloud_url}\n"
            "Please ensure the cloud server is running and accessible."
        )
    
    try:
        vprint("[cyan]☁️ Cloud Native Mode: Using remote Demucs service...[/cyan]")
        separate_audio_cloud(cloud_url)
        vprint("[green]✨ Audio separation completed (cloud native)![/green]")
    except Exception as e:
        raise RuntimeError(
            f"Cloud separation failed: {e}\n"
            "Please check the cloud server status."
        )

if __name__ == "__main__":
    demucs_audio()
