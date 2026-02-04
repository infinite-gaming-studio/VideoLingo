#!/usr/bin/env python3
"""
Step 2: GPU 检查
检查 GPU 可用性
"""

import subprocess
import shutil
import os


def check_gpu():
    """检查 GPU 可用性（支持多种环境）"""
    
    # 方法 1: 尝试使用 nvidia-smi（标准方法）
    nvidia_smi_path = shutil.which('nvidia-smi')
    if nvidia_smi_path:
        try:
            result = subprocess.run([nvidia_smi_path], capture_output=True, text=True)
            if result.returncode == 0:
                print(result.stdout)
                print("\n✅ GPU detected via nvidia-smi!\n")
                return True
        except Exception:
            pass
    
    # 方法 2: 检查 NVIDIA 驱动文件（Colab/Kaggle 环境）
    if os.path.exists('/proc/driver/nvidia/version'):
        try:
            with open('/proc/driver/nvidia/version', 'r') as f:
                nvidia_info = f.read()
                if nvidia_info:
                    print("NVIDIA Driver Info:")
                    print(nvidia_info[:500])
                    print("\n✅ NVIDIA driver detected!\n")
                    return True
        except Exception:
            pass
    
    # 方法 3: 检查 CUDA 设备（Colab/Kaggle）
    cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES')
    if cuda_devices:
        print(f"CUDA_VISIBLE_DEVICES: {cuda_devices}")
        print("\n✅ CUDA device detected!\n")
        return True
    
    # 方法 4: 检查 PyTorch CUDA（如果已安装）
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            print(f"PyTorch CUDA available: {gpu_name}")
            print("\n✅ GPU detected via PyTorch!\n")
            return True
    except ImportError:
        pass
    except Exception:
        pass
    
    # 所有方法都失败
    print("\n⚠️  WARNING: No GPU detected")
    print("   - nvidia-smi not found in PATH")
    print("   - NVIDIA driver not detected")
    print("   - CUDA not available")
    print("   Server will run in CPU mode (slow)\n")
    return False


if __name__ == "__main__":
    check_gpu()
