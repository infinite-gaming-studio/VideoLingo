"""
VideoLingo Cloud Package
Unified cloud API for ASR and audio separation

Structure:
- client/: Client code for connecting to cloud services
- server/: FastAPI server implementation
- shared/: Shared models and utilities

Usage:
    # Client usage
    from videolingo_cloud.client import UnifiedCloudClient, get_cloud_url
    
    # Server usage
    from videolingo_cloud.server import app, run_server
"""

from videolingo_cloud._version import SERVER_VERSION

# Backward compatibility - re-export from client module
from videolingo_cloud.client import (
    UnifiedCloudClient,
    get_cloud_url,
    get_cloud_token,
    check_cloud_connection,
    transcribe_audio_cloud,
    separate_audio_cloud,
    transcribe_audio_cloud_compatible,
    separate_audio_cloud_compatible,
    get_server_info,
)

__version__ = SERVER_VERSION
__all__ = [
    "SERVER_VERSION",
    "UnifiedCloudClient",
    "get_cloud_url",
    "get_cloud_token",
    "check_cloud_connection",
    "transcribe_audio_cloud",
    "separate_audio_cloud",
    "transcribe_audio_cloud_compatible",
    "separate_audio_cloud_compatible",
    "get_server_info",
]
