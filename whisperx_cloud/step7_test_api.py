#!/usr/bin/env python3
"""
Step 7: 测试 API
测试 API 连接
"""

import requests
import os


def test_api():
    """测试 API 连接"""
    
    # 加载配置
    try:
        from config import SERVER_PORT
    except ImportError:
        SERVER_PORT = 8000
    
    SERVER_PORT = int(os.environ.get('SERVER_PORT', SERVER_PORT))
    
    # 读取 URL
    try:
        with open('server_url.txt', 'r') as f:
            API_URL = f.read().strip()
    except:
        API_URL = f"http://localhost:{SERVER_PORT}"
    
    print(f"Testing: {API_URL}")
    print("-"*50)
    
    # 健康检查
    try:
        response = requests.get(f"{API_URL}/", timeout=10)
        data = response.json()
        
        print("✅ Health Check PASSED\n")
        print(f"   Status: {data.get('status')}")
        print(f"   Platform: {data.get('platform')}")
        print(f"   Device: {data.get('device')}")
        if data.get('gpu_memory_gb'):
            print(f"   GPU Memory: {data['gpu_memory_gb']:.2f} GB")
        print(f"   Models Cached: {data.get('models_cached', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if server is running (previous cell)")
        print("2. Try waiting a bit longer and re-run")
        print("3. Check ngrok status")
        return False


if __name__ == "__main__":
    test_api()
