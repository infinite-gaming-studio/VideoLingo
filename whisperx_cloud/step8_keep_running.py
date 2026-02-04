#!/usr/bin/env python3
"""
Step 8: 保持运行
保持服务器运行 (⚠️ 不要停止此脚本!)
"""

import time
import requests


def keep_running():
    """保持服务器运行"""
    
    # 读取 URL
    try:
        with open('server_url.txt', 'r') as f:
            API_URL = f.read().strip()
    except:
        API_URL = "http://localhost:8000"
    
    print("💓 Server is running...\n")
    print("Press Ctrl+C to stop\n")
    
    try:
        count = 0
        while True:
            time.sleep(30)
            count += 1
            
            # 每分钟检查一次健康状态
            if count % 2 == 0:
                try:
                    r = requests.get(f"{API_URL}/", timeout=5)
                    if r.status_code == 200:
                        print(f"✅ {time.strftime('%H:%M:%S')} - Server healthy")
                    else:
                        print(f"⚠️  {time.strftime('%H:%M:%S')} - Status: {r.status_code}")
                except:
                    print(f"⚠️  {time.strftime('%H:%M:%S')} - Health check failed")
            else:
                print(f"💓 {time.strftime('%H:%M:%S')} - Running...")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping server...")
        try:
            from pyngrok import ngrok
            ngrok.kill()
        except:
            pass
        print("✅ Server stopped")


if __name__ == "__main__":
    keep_running()
