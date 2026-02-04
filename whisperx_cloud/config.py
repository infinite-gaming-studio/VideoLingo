#!/usr/bin/env python3
"""
WhisperX Cloud API Server - Configuration
用户可编辑的配置文件
"""

import os

# ============================================
# CONFIGURATION - 在这里配置你的参数
# ============================================

# ngrok 认证令牌 (必需 - 从 https://dashboard.ngrok.com 获取)
NGROK_AUTH_TOKEN = ""

# API 服务端口
SERVER_PORT = 8000

# 默认 Whisper 模型
DEFAULT_MODEL = "large-v3"

# 是否启用说话人分离 (需要更多 GPU 内存)
ENABLE_DIARIZATION = False

# HuggingFace 镜像 (中国大陆用户可设置为 "https://hf-mirror.com")
HF_ENDPOINT = "https://huggingface.co"


def load_config():
    """加载配置并设置环境变量"""
    # 设置 HuggingFace 端点
    os.environ['HF_ENDPOINT'] = HF_ENDPOINT
    
    # 从环境变量覆盖（如果存在）
    global NGROK_AUTH_TOKEN, SERVER_PORT, DEFAULT_MODEL, ENABLE_DIARIZATION, HF_ENDPOINT
    
    NGROK_AUTH_TOKEN = os.environ.get('NGROK_AUTH_TOKEN', NGROK_AUTH_TOKEN)
    SERVER_PORT = int(os.environ.get('SERVER_PORT', SERVER_PORT))
    DEFAULT_MODEL = os.environ.get('DEFAULT_MODEL', DEFAULT_MODEL)
    ENABLE_DIARIZATION = os.environ.get('ENABLE_DIARIZATION', str(ENABLE_DIARIZATION)).lower() == 'true'
    HF_ENDPOINT = os.environ.get('HF_ENDPOINT', HF_ENDPOINT)
    
    print("⚙️ Configuration loaded")
    print(f"   Model: {DEFAULT_MODEL}")
    print(f"   Port: {SERVER_PORT}")
    print(f"   HF Endpoint: {HF_ENDPOINT}")
    
    return {
        'NGROK_AUTH_TOKEN': NGROK_AUTH_TOKEN,
        'SERVER_PORT': SERVER_PORT,
        'DEFAULT_MODEL': DEFAULT_MODEL,
        'ENABLE_DIARIZATION': ENABLE_DIARIZATION,
        'HF_ENDPOINT': HF_ENDPOINT
    }


if __name__ == "__main__":
    load_config()
