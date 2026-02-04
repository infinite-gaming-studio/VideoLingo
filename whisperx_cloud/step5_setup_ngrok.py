#!/usr/bin/env python3
"""
Step 5: 配置 ngrok
设置 ngrok 认证令牌
"""

from pyngrok import ngrok


def setup_ngrok():
    """配置 ngrok"""
    # 加载配置
    try:
        from config import NGROK_AUTH_TOKEN
    except ImportError:
        NGROK_AUTH_TOKEN = ""
    
    # 从环境变量获取
    import os
    NGROK_AUTH_TOKEN = os.environ.get('NGROK_AUTH_TOKEN', NGROK_AUTH_TOKEN)
    
    if not NGROK_AUTH_TOKEN:
        print("❌ ERROR: NGROK_AUTH_TOKEN is not set!")
        print("\n请按以下步骤获取:")
        print("1. 访问 https://dashboard.ngrok.com/signup")
        print("2. 注册并登录")
        print("3. 访问 https://dashboard.ngrok.com/get-started/your-authtoken")
        print("4. 复制 token 到 config.py 文件中的 NGROK_AUTH_TOKEN 变量")
        raise ValueError("NGROK_AUTH_TOKEN required")
    
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    print("✅ ngrok configured successfully!")
    return True


if __name__ == "__main__":
    setup_ngrok()
