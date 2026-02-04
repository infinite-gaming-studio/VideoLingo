#!/usr/bin/env python3
"""
Step 1: 环境检测与设置
检测运行平台 (Colab/Kaggle/Local)
"""

import sys
import os


def detect_environment():
    """检测运行环境"""
    # 检测平台
    IN_COLAB = 'google.colab' in sys.modules
    IN_KAGGLE = os.path.exists('/kaggle')
    IN_LOCAL = not IN_COLAB and not IN_KAGGLE
    
    print("🔍 Environment Detection:")
    print(f"   Google Colab: {IN_COLAB}")
    print(f"   Kaggle: {IN_KAGGLE}")
    print(f"   Local: {IN_LOCAL}")
    
    # 加载配置
    try:
        from config import HF_ENDPOINT
        os.environ['HF_ENDPOINT'] = HF_ENDPOINT
    except ImportError:
        pass
    
    # Kaggle 特殊处理
    if IN_KAGGLE:
        print("\n📌 Kaggle Instructions:")
        print("   1. Settings → Accelerator → GPU T4 x2")
        print("   2. Internet must be ON for ngrok")
    
    return {
        'IN_COLAB': IN_COLAB,
        'IN_KAGGLE': IN_KAGGLE,
        'IN_LOCAL': IN_LOCAL
    }


if __name__ == "__main__":
    detect_environment()
