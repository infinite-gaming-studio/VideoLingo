"""
IndexTTS2 API Client for VideoLingo
Supports voice cloning via reference audio with configurable emotion intensity.

API Documentation: See indextts-api.md
"""

import os
import time
import requests
from pathlib import Path
from typing import Optional, Tuple
from core.utils import *
from core.utils.models import _AUDIO_REFERS_DIR
from core._1_ytdlp import find_video_files


class IndexTTSConfig:
    """Configuration wrapper for IndexTTS settings."""
    
    def __init__(self):
        self.api_url = self._load_url()
        self.api_token = load_key("indextts.api_token", "")
        self.emo_alpha = load_key("indextts.emo_alpha", 1.0)
        self.refer_mode = load_key("indextts.refer_mode", 2)
        self.timeout = load_key("indextts.timeout", 60)
    
    def _load_url(self) -> str:
        """Load and normalize API URL."""
        url = load_key("indextts.api_url", "http://localhost:8000")
        # Remove trailing slash
        url = url.rstrip('/')
        return url
    
    @property
    def tts_endpoint(self) -> str:
        return f"{self.api_url}/api/tts"
    
    @property
    def health_endpoint(self) -> str:
        return f"{self.api_url}/api/health"
    
    @property
    def auth_headers(self) -> dict:
        """Get authorization headers if token is configured."""
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        return {}


def check_indextts_health(config: Optional[IndexTTSConfig] = None) -> dict:
    """
    Check IndexTTS service health status.
    
    Returns:
        dict: Health status with keys: status, model, device, loaded
    Raises:
        requests.RequestException: If service is unreachable
    """
    config = config or IndexTTSConfig()
    
    try:
        response = requests.get(
            config.health_endpoint,
            headers=config.auth_headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            raise RuntimeError(
                "IndexTTS API authentication failed. "
                "Please check your API token configuration."
            )
        raise
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Cannot connect to IndexTTS service at {config.api_url}. "
            "Please ensure the service is running."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"Health check timed out after 10s. "
            f"Service at {config.api_url} may be starting up."
        )


@except_handler("Failed to generate audio using IndexTTS", retry=3, delay=1)
def indextts_tts(
    text: str,
    save_path: str,
    ref_audio_path: str,
    emo_alpha: float = 1.0,
    api_url: Optional[str] = None
) -> bool:
    """
    Generate speech using IndexTTS2 API.
    
    Args:
        text: Text to synthesize
        save_path: Output audio file path
        ref_audio_path: Reference audio file for voice cloning
        emo_alpha: Emotion intensity (0.0 - 2.0, default 1.0)
        api_url: Optional custom API URL (uses config if not provided)
    
    Returns:
        bool: True if successful
    
    Raises:
        FileNotFoundError: If reference audio doesn't exist
        requests.RequestException: If API call fails
        ValueError: If emo_alpha is out of range
    """
    # Validate inputs
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    
    if emo_alpha < 0.0 or emo_alpha > 2.0:
        raise ValueError(f"emo_alpha must be between 0.0 and 2.0, got {emo_alpha}")
    
    ref_path = Path(ref_audio_path)
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")
    
    # Setup API endpoint
    config = IndexTTSConfig()
    url = api_url or config.api_url
    tts_url = f"{url.rstrip('/')}/api/tts"
    
    # Prepare multipart form data
    with open(ref_path, 'rb') as audio_file:
        files = {
            'spk_audio': (ref_path.name, audio_file, 'audio/wav')
        }
        data = {
            'text': text.strip(),
            'emo_alpha': str(emo_alpha)
        }
        
        # Prepare headers (Authorization if token configured)
        headers = config.auth_headers
        
        rprint(f"[blue]🎙️ Calling IndexTTS API...")
        rprint(f"[dim]   URL: {tts_url}")
        rprint(f"[dim]   Text length: {len(text)} chars")
        rprint(f"[dim]   Emo alpha: {emo_alpha}")
        rprint(f"[dim]   Ref audio: {ref_path.name}")
        if config.api_token:
            rprint(f"[dim]   Auth: Bearer token configured")
        
        response = requests.post(
            tts_url,
            headers=headers,
            files=files,
            data=data,
            timeout=config.timeout
        )
    
    # Handle response
    if response.status_code == 200:
        # Success - save audio
        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        rprint(f"[green]✅ Audio saved: {output_path}")
        return True
    
    elif response.status_code == 401:
        raise RuntimeError(
            "IndexTTS API authentication failed (401). "
            "Please check your API token configuration."
        )
    
    elif response.status_code == 503:
        error_data = response.json()
        raise RuntimeError(f"IndexTTS model not loaded: {error_data.get('error', 'Unknown error')}")
    
    else:
        try:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
        except:
            error_msg = response.text or f"HTTP {response.status_code}"
        
        raise RuntimeError(f"IndexTTS API error: {error_msg}")


def _find_default_ref_audio(character: str) -> Path:
    """
    Find default reference audio for a character (Mode 1).
    
    Looks in common locations for reference audio files.
    """
    # Search paths
    search_dirs = [
        Path("output/audio/refers"),
        Path("models/indextts/refers"),
        Path("refers"),
    ]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        # Look for character-specific files
        patterns = [
            f"{character}*.wav",
            f"{character}*.mp3",
            "*.wav",
            "*.mp3"
        ]
        
        for pattern in patterns:
            files = list(search_dir.glob(pattern))
            if files:
                return files[0]
    
    raise FileNotFoundError(
        f"No default reference audio found for character '{character}'. "
        f"Please place a reference audio file in output/audio/refers/"
    )


def _get_mode2_ref_audio() -> str:
    """Get reference audio for Mode 2 (first video segment)."""
    ref_path = Path(_AUDIO_REFERS_DIR) / "1.wav"
    
    if not ref_path.exists():
        # Try to extract reference audio
        try:
            from core._9_refer_audio import extract_refer_audio_main
            rprint(f"[yellow]⚠️ Reference audio not found, extracting...[/yellow]")
            extract_refer_audio_main()
        except Exception as e:
            rprint(f"[red]❌ Failed to extract reference audio: {e}[/red]")
            raise
    
    if not ref_path.exists():
        raise FileNotFoundError(
            f"Mode 2 reference audio not found at {ref_path}. "
            "Please ensure video has been processed."
        )
    
    return str(ref_path)


def _get_mode3_ref_audio(number: int) -> str:
    """Get reference audio for Mode 3 (segment-specific)."""
    ref_path = Path(_AUDIO_REFERS_DIR) / f"{number}.wav"
    
    if not ref_path.exists():
        # Fallback to mode 2
        rprint(f"[yellow]⚠️ Segment {number} ref audio not found, falling back to mode 2[/yellow]")
        return _get_mode2_ref_audio()
    
    return str(ref_path)


def indextts_tts_for_videolingo(
    text: str,
    save_as: str,
    number: int,
    task_df
) -> bool:
    """
    IndexTTS integration for VideoLingo with 3 reference modes.
    
    Reference Modes:
        1. Use configured default reference audio
        2. Use first segment from video as reference
        3. Use corresponding segment as reference
    
    Args:
        text: Text to synthesize
        save_as: Output file path
        number: Segment number
        task_df: Task DataFrame with segment info
    
    Returns:
        bool: True if successful
    """
    config = IndexTTSConfig()
    
    # Pre-flight health check
    try:
        health = check_indextts_health(config)
        if not health.get('loaded', False):
            raise RuntimeError("IndexTTS model is not loaded yet")
        rprint(f"[dim]🟢 IndexTTS service ready: {health.get('device', 'unknown device')}")
    except ConnectionError as e:
        rprint(f"[bold red]❌ {e}[/bold red]")
        raise
    
    # Determine reference audio based on mode
    refer_mode = config.refer_mode
    
    if refer_mode == 1:
        # Mode 1: Default reference audio
        character = load_key("indextts.character", "default")
        ref_audio = _find_default_ref_audio(character)
        rprint(f"[blue]📀 Using default reference (Mode 1): {character}")
        
    elif refer_mode == 2:
        # Mode 2: First video segment
        ref_audio = _get_mode2_ref_audio()
        rprint(f"[blue]📀 Using video first segment (Mode 2)")
        
    elif refer_mode == 3:
        # Mode 3: Segment-specific reference
        ref_audio = _get_mode3_ref_audio(number)
        rprint(f"[blue]📀 Using segment-specific reference (Mode 3): #{number}")
        
    else:
        raise ValueError(f"Invalid refer_mode: {refer_mode}. Choose 1, 2, or 3.")
    
    # Call TTS API
    success = indextts_tts(
        text=text,
        save_path=save_as,
        ref_audio_path=str(ref_audio),
        emo_alpha=config.emo_alpha
    )
    
    # Fallback for mode 3: if segment-specific fails, try mode 2
    if not success and refer_mode == 3:
        rprint(f"[yellow]⚠️ Mode 3 failed, falling back to Mode 2...[/yellow]")
        ref_audio = _get_mode2_ref_audio()
        success = indextts_tts(
            text=text,
            save_path=save_as,
            ref_audio_path=str(ref_audio),
            emo_alpha=config.emo_alpha
        )
    
    return success


def test_indextts_connection() -> bool:
    """Test connection to IndexTTS service."""
    try:
        config = IndexTTSConfig()
        health = check_indextts_health(config)
        rprint(f"[green]✅ IndexTTS connection successful[/green]")
        rprint(f"[dim]   Model: {health.get('model', 'unknown')}")
        rprint(f"[dim]   Device: {health.get('device', 'unknown')}")
        rprint(f"[dim]   Loaded: {health.get('loaded', False)}")
        return True
    except Exception as e:
        rprint(f"[red]❌ IndexTTS connection failed: {e}[/red]")
        return False


if __name__ == "__main__":
    # Test connection
    test_indextts_connection()
