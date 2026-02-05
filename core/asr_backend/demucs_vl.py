"""
VideoLingo Demucs Audio Separation Module
Supports both local GPU processing and cloud-native remote processing

Cloud Native Mode:
- When cloud_native.enabled=true in config.yaml
- All separation processing is done via remote Demucs cloud service
- No local torch/demucs dependencies required

Local Mode (Legacy):
- When cloud_native.enabled=false or not set
- Uses local GPU for separation processing
- Requires torch, demucs, and other GPU dependencies
"""

import os
from rich.console import Console
from rich import print as rprint
from typing import Optional
from core.utils.models import *

console = Console()

# Cloud API configuration
DEMUCS_CLOUD_URL = os.getenv("DEMUCS_CLOUD_URL", "")


def is_cloud_native():
    """Check if cloud native mode is enabled in config"""
    try:
        from core.utils import load_key
        return load_key("cloud_native.enabled", False)
    except:
        return False


def is_cloud_separation_enabled():
    """Check if cloud separation feature is enabled"""
    try:
        from core.utils import load_key
        if not load_key("cloud_native.enabled", False):
            return False
        return load_key("cloud_native.features.separation", True)
    except:
        return False

def get_cloud_url() -> str:
    """Get cloud URL from environment or config"""
    if DEMUCS_CLOUD_URL:
        return DEMUCS_CLOUD_URL.rstrip('/')
    
    try:
        from core.utils import load_key
        # Try demucs_cloud_url first, fallback to whisperX_cloud_url
        url = load_key("demucs_cloud_url", "")
        if not url:
            url = load_key("whisper.whisperX_cloud_url", "")
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

def separate_audio_local():
    """Local Demucs processing (requires demucs package)"""
    try:
        import torch
        from demucs.pretrained import get_model
        from demucs.audio import save_audio
        from torch.cuda import is_available as is_cuda_available
        from demucs.api import Separator
        from demucs.apply import BagOfModels
        import gc
    except ImportError as e:
        raise ImportError(
            "Local Demucs processing requires 'demucs' package. "
            "Install with: pip install demucs\n"
            "Or use cloud mode by setting whisper.whisperX_cloud_url in config.yaml"
        ) from e
    
    class PreloadedSeparator(Separator):
        def __init__(self, model: BagOfModels, shifts: int = 1, overlap: float = 0.25,
                     split: bool = True, segment: Optional[int] = None, jobs: int = 0):
            self._model, self._audio_channels, self._samplerate = model, model.audio_channels, model.samplerate
            device = "cuda" if is_cuda_available() else "mps" if torch.backends.mps.is_available() else "cpu"
            self.update_parameter(device=device, shifts=shifts, overlap=overlap, split=split,
                                segment=segment, jobs=jobs, progress=True, callback=None, callback_arg=None)
    
    console.print("🤖 Loading <htdemucs> model...")
    model = get_model('htdemucs')
    separator = PreloadedSeparator(model=model, shifts=1, overlap=0.25)
    
    console.print("🎵 Separating audio...")
    _, outputs = separator.separate_audio_file(_RAW_AUDIO_FILE)
    
    kwargs = {"samplerate": model.samplerate, "bitrate": 128, "preset": 2, 
             "clip": "rescale", "as_float": False, "bits_per_sample": 16}
    
    console.print("🎤 Saving vocals track...")
    save_audio(outputs['vocals'].cpu(), _VOCAL_AUDIO_FILE, **kwargs)
    
    console.print("🎹 Saving background music...")
    background = sum(audio for source, audio in outputs.items() if source != 'vocals')
    save_audio(background.cpu(), _BACKGROUND_AUDIO_FILE, **kwargs)
    
    # Clean up memory
    del outputs, background, model, separator
    gc.collect()

def separate_audio_cloud(cloud_url: str = None):
    """Cloud Demucs processing via unified API"""
    url = cloud_url or get_cloud_url()
    
    if not url:
        raise ValueError(
            "Cloud URL not configured. Set whisper.whisperX_cloud_url in config.yaml "
            "or DEMUCS_CLOUD_URL env var"
        )
    
    try:
        # Try unified client first
        from whisperx_cloud.unified_client import separate_audio_cloud as cloud_separate
        cloud_separate(
            audio_file=_RAW_AUDIO_FILE,
            vocals_output=_VOCAL_AUDIO_FILE,
            background_output=_BACKGROUND_AUDIO_FILE,
            cloud_url=url
        )
    except ImportError:
        # Fallback: inline implementation
        import requests
        import base64
        
        console.print(f"🚀 Using cloud Demucs: {url}")
        console.print("🎵 Sending audio for separation...")
        
        with open(_RAW_AUDIO_FILE, 'rb') as f:
            files = {'audio': (os.path.basename(_RAW_AUDIO_FILE), f, 'audio/wav')}
            data = {'return_files': 'true'}
            
            response = requests.post(
                f"{url}/separation/separate",
                files=files,
                data=data,
                timeout=300
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
                console.print(f"[green]✅ Vocals saved[/green]")
            
            background_b64 = result.get('background_base64')
            if background_b64:
                os.makedirs(os.path.dirname(_BACKGROUND_AUDIO_FILE) or '.', exist_ok=True)
                with open(_BACKGROUND_AUDIO_FILE, 'wb') as f:
                    f.write(base64.b64decode(background_b64))
                console.print(f"[green]✅ Background saved[/green]")

def demucs_audio():
    """
    Main entry point for Demucs audio separation
    Automatically chooses between local and cloud processing based on configuration
    """
    if os.path.exists(_VOCAL_AUDIO_FILE) and os.path.exists(_BACKGROUND_AUDIO_FILE):
        rprint(f"[yellow]⚠️ {_VOCAL_AUDIO_FILE} and {_BACKGROUND_AUDIO_FILE} already exist, skip Demucs processing.[/yellow]")
        return
    
    os.makedirs(_AUDIO_DIR, exist_ok=True)
    
    # Check if cloud native mode is enabled
    cloud_native_mode = is_cloud_native()
    cloud_separation = is_cloud_separation_enabled()
    cloud_url = get_cloud_url()
    
    if cloud_native_mode:
        # Cloud Native Mode: Must use cloud processing
        if not cloud_url:
            raise ValueError(
                "Cloud Native Mode is enabled but no cloud URL is configured.\n"
                "Please set cloud_native.cloud_url in config.yaml"
            )
        
        if not check_cloud_available(cloud_url):
            raise ConnectionError(
                f"Cloud Native Mode is enabled but cloud service is not available at {cloud_url}\n"
                "Please ensure the cloud server is running and accessible."
            )
        
        try:
            console.print("[cyan]☁️ Cloud Native Mode: Using remote Demucs service...[/cyan]")
            separate_audio_cloud(cloud_url)
            console.print("[green]✨ Audio separation completed (cloud native)![/green]")
            return
        except Exception as e:
            raise RuntimeError(
                f"Cloud separation failed in Cloud Native Mode: {e}\n"
                "Please check the cloud server status or disable cloud_native mode."
            )
    
    # Legacy Mode: Try cloud first, then fallback to local
    if cloud_url and check_cloud_available(cloud_url):
        # Use cloud processing
        try:
            separate_audio_cloud(cloud_url)
            console.print("[green]✨ Audio separation completed (cloud)![/green]")
            return
        except Exception as e:
            rprint(f"[yellow]⚠️ Cloud processing failed: {e}[/yellow]")
            rprint("[yellow]Falling back to local processing...[/yellow]")
    
    # Use local processing
    try:
        separate_audio_local()
        console.print("[green]✨ Audio separation completed (local)![/green]")
    except ImportError as e:
        rprint(f"[red]❌ {e}[/red]")
        rprint("[yellow]To use cloud Demucs:[/yellow]")
        rprint(" 1. Deploy unified server using whisperx_cloud/Unified_Cloud_Server.ipynb")
        rprint(" 2. Set whisper.whisperX_cloud_url in config.yaml")
        rprint("[yellow]Or install demucs locally:[/yellow]")
        rprint(" pip install demucs")
        raise

if __name__ == "__main__":
    demucs_audio()
