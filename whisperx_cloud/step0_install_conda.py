#!/usr/bin/env python3
"""
Step 0: 安装 Conda (如果需要)
在 Colab/Kaggle 等环境中自动安装 Miniconda
"""

import os
import sys
import subprocess
import platform


def check_conda():
    """检查 Conda 是否可用"""
    try:
        result = subprocess.run(['conda', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Conda already installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    return False


def install_miniconda():
    """安装 Miniconda"""
    print("📥 Installing Miniconda...")
    
    # 检测系统
    system = platform.system().lower()
    machine = platform.machine()
    
    # 下载链接
    if system == 'linux':
        if '64' in machine:
            url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
        else:
            url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
    elif system == 'darwin':  # macOS
        url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
    else:
        raise RuntimeError(f"Unsupported system: {system}")
    
    # 安装路径
    install_path = os.path.expanduser("~/miniconda3")
    
    # 下载安装脚本
    print(f"   Downloading from {url}...")
    subprocess.run(["wget", "-q", url, "-O", "/tmp/miniconda.sh"], check=True)
    
    # 运行安装脚本
    print(f"   Installing to {install_path}...")
    subprocess.run(["bash", "/tmp/miniconda.sh", "-b", "-p", install_path], check=True)
    
    # 初始化 shell
    print("   Initializing conda...")
    subprocess.run([f"{install_path}/bin/conda", "init", "bash"], check=True)
    
    # 添加 PATH
    os.environ['PATH'] = f"{install_path}/bin:" + os.environ.get('PATH', '')
    
    # 清理
    os.remove("/tmp/miniconda.sh")
    
    print("✅ Miniconda installed successfully!")
    print(f"   Location: {install_path}")
    return True


def setup_conda():
    """设置 Conda 环境"""
    if check_conda():
        return True
    
    # 检测是否在 Colab/Kaggle
    IN_COLAB = 'google.colab' in sys.modules
    IN_KAGGLE = os.path.exists('/kaggle')
    
    if IN_COLAB or IN_KAGGLE:
        print("🔍 Running in cloud environment, installing Miniconda...")
        try:
            install_miniconda()
            return True
        except Exception as e:
            print(f"❌ Failed to install Miniconda: {e}")
            print("\n⚠️  Will try to use pip instead...")
            return False
    else:
        print("❌ ERROR: Conda is not installed!")
        print("\n请按以下步骤安装 Conda:")
        print("1. 安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html")
        print("2. 或使用 Anaconda: https://www.anaconda.com/download")
        return False


if __name__ == "__main__":
    setup_conda()
