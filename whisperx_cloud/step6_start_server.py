#!/usr/bin/env python3
"""
Step 6: 启动服务器
启动 API 服务器和 ngrok 隧道
"""

import subprocess
import time
import os
import signal
import sys

from pyngrok import ngrok


def start_server():
    """启动 API 服务器和 ngrok 隧道"""
    
    # 加载配置
    try:
        from config import SERVER_PORT, HF_ENDPOINT
    except ImportError:
        SERVER_PORT = 8000
        HF_ENDPOINT = "https://huggingface.co"
    
    # 从环境变量获取
    SERVER_PORT = int(os.environ.get('SERVER_PORT', SERVER_PORT))
    HF_ENDPOINT = os.environ.get('HF_ENDPOINT', HF_ENDPOINT)
    
    # 清理旧进程
    print("🧹 Cleaning up old processes...")
    subprocess.run("pkill -f whisperx_server.py 2>/dev/null || true", shell=True)
    subprocess.run("pkill -f ngrok 2>/dev/null || true", shell=True)
    time.sleep(2)
    
    # 关闭现有 ngrok 隧道
    try:
        ngrok.kill()
    except:
        pass
    
    # 设置环境变量
    os.environ['PORT'] = str(SERVER_PORT)
    os.environ['HF_ENDPOINT'] = HF_ENDPOINT
    
    # 启动服务器
    print("\n🚀 Starting WhisperX API server...")
    server_process = subprocess.Popen(
        [sys.executable, 'whisperx_server.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None
    )
    
    # 等待服务器启动
    print("⏳ Waiting for server to start (10s)...")
    time.sleep(10)
    
    # 启动 ngrok
    print("\n🌐 Creating ngrok tunnel...")
    try:
        public_url = ngrok.connect(SERVER_PORT, "http")
        
        print("\n" + "="*60)
        print("✅ SERVER IS RUNNING!")
        print("="*60)
        print(f"\n🌐 Public URL: {public_url}")
        print(f"🔗 API Endpoint: {public_url}/transcribe")
        print(f"🏥 Health Check: {public_url}/")
        print(f"📊 Stats: {public_url}/stats")
        print("\n" + "="*60)
        print("📋 Copy the Public URL to VideoLingo config!")
        print("="*60 + "\n")
        
        # 保存 URL
        with open('server_url.txt', 'w') as f:
            f.write(str(public_url))
        
        return str(public_url)
        
    except Exception as e:
        print(f"\n❌ Error starting ngrok: {e}")
        print("\nTrying local tunnel alternative...")
        return None


if __name__ == "__main__":
    start_server()
