#!/usr/bin/env python3
"""
Step 2: GPU 检查
检查 GPU 可用性
"""

import subprocess


def check_gpu():
    """检查 GPU 可用性"""
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    print(result.stdout)
    
    if result.returncode != 0:
        print("\n⚠️  WARNING: No GPU detected or nvidia-smi not found")
        print("   Server will run in CPU mode (slow)\n")
        return False
    else:
        print("\n✅ GPU detected!\n")
        return True


if __name__ == "__main__":
    check_gpu()
