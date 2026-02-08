"""
VideoLingo Cloud Client
Client for connecting to VideoLingo Cloud API
"""

from .client import (
    UnifiedCloudClient,
    get_cloud_url,
    get_cloud_token,
    check_cloud_connection,
    transcribe_audio_cloud,
    separate_audio_cloud,
    transcribe_audio_cloud_compatible,
    separate_audio_cloud_compatible,
    get_server_info,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)

__all__ = [
    "UnifiedCloudClient",
    "get_cloud_url",
    "get_cloud_token",
    "check_cloud_connection",
    "transcribe_audio_cloud",
    "separate_audio_cloud",
    "transcribe_audio_cloud_compatible",
    "separate_audio_cloud_compatible",
    "get_server_info",
    "DEFAULT_TIMEOUT",
    "MAX_RETRIES",
    "RETRY_DELAY",
]
