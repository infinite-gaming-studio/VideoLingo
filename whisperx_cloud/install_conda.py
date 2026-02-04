#!/usr/bin/env python3
"""
WhisperX Cloud API Server - Conda Installation Script
Reference: VideoLingo/install.py

This script provides guided installation for the WhisperX Cloud server using conda.
It handles environment creation, PyTorch CUDA installation, and dependency setup.

Usage:
    python install_conda.py

Requirements:
    - conda (Anaconda or Miniconda)
    - NVIDIA GPU with CUDA support (recommended)
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

# ASCII Art Logo
ASCII_LOGO = r"""
__     ___     _            _     _                    _                 _
\ \   / (_) __| | ___  ___ | |   (_)_ __   __ _  ___  | | ___   ___ __ _| |_
 \ \ / /| |/ _` |/ _ \/ _ \| |   | | '_ \ / _` |/ _ \ | |/ _ \ / __/ _` | __|
  \ V / | | (_| |  __/ (_) | |___| | | | | (_| | (_) || | (_) | (_| (_| | |_
   \_/  |_|
__,_|\___|\___/|_____|_|_| |_|\__, |\___/ |___\___/ \___\__,_|\__|
                                          |___/
                          Cloud API Server
"""


def run_command(cmd, check=True, capture_output=False):
    """Run shell command with error handling"""
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
            return result
        else:
            subprocess.run(cmd, shell=True, check=check)
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        print(f"   Error: {e}")
        return None


def check_conda():
    """Check if conda is installed"""
    result = run_command("conda --version", check=False, capture_output=True)
    if result and result.returncode == 0:
        print(f"✅ Conda detected: {result.stdout.strip()}")
        return True
    else:
        print("❌ Conda not found!")
        print("\n📥 Please install Miniconda or Anaconda:")
        print("   - Miniconda: https://docs.conda.io/en/latest/miniconda.html")
        print("   - Anaconda: https://www.anaconda.com/download")
        print("\n   After installation, restart your terminal and run this script again.")
        return False


def check_nvidia_gpu():
    """Check for NVIDIA GPU"""
    print("\n🔍 Checking GPU...")
    result = run_command("nvidia-smi", check=False, capture_output=True)

    if result and result.returncode == 0:
        print("✅ NVIDIA GPU detected:")
        # Extract GPU name from nvidia-smi output
        for line in result.stdout.split('\n'):
            if 'NVIDIA' in line or 'RTX' in line or 'Tesla' in line or 'A100' in line:
                print(f"   {line.strip()}")
        return True
    else:
        print("⚠️  No NVIDIA GPU detected or nvidia-smi not found")
        print("   Server will run in CPU mode (significantly slower)")
        return False


def create_conda_env(env_name="whisperx-cloud", use_gpu=True):
    """Create conda environment"""
    print(f"\n📦 Creating conda environment: {env_name}")

    # Determine Python version
    python_version = "3.10"

    # Create environment command
    cmd = f"conda create -n {env_name} python={python_version} -y"

    print(f"   Python version: {python_version}")
    run_command(cmd)

    return env_name


def install_pytorch(env_name, use_gpu=True):
    """Install PyTorch with appropriate CUDA version"""
    print("\n📦 Installing PyTorch...")

    # Detect CUDA version
    cuda_version = None
    if use_gpu:
        result = run_command("nvidia-smi", capture_output=True)
        if result:
            for line in result.stdout.split('\n'):
                if 'CUDA Version' in line:
                    # Extract CUDA version
                    import re
                    match = re.search(r'CUDA Version:\s*(\d+\.\d+)', line)
                    if match:
                        cuda_version = match.group(1)
                        break

    # Choose PyTorch installation command
    if use_gpu and cuda_version:
        # Use CUDA 11.8 for compatibility (works with CUDA 11.8 and 12.x)
        print(f"   Installing PyTorch with CUDA 11.8 support")
        print(f"   (Compatible with system CUDA {cuda_version})")
        cmd = (
            f"conda run -n {env_name} conda install pytorch=2.0.0 "
            f"torchaudio=2.0.0 pytorch-cuda=11.8 -c pytorch -c nvidia -y"
        )
    else:
        print("   Installing CPU-only PyTorch")
        cmd = (
            f"conda run -n {env_name} conda install pytorch=2.0.0 "
            f"torchaudio=2.0.0 cpuonly -c pytorch -y"
        )

    run_command(cmd)


def install_dependencies(env_name):
    """Install remaining dependencies via pip"""
    print("\n📦 Installing additional dependencies...")

    requirements_file = Path(__file__).parent / "requirements.txt"

    if requirements_file.exists():
        cmd = f"conda run -n {env_name} pip install -r {requirements_file}"
        run_command(cmd)
    else:
        print("⚠️  requirements.txt not found, installing core packages...")
        packages = [
            "whisperx @ git+https://github.com/m-bain/whisperx.git@7307306a9d8dd0d261e588cc933322454f853853",
            "faster-whisper==1.0.0",
            "ctranslate2==4.4.0",
            "transformers==4.39.3",
            "librosa==0.10.2.post1",
            "soundfile>=0.12.1",
            "numpy==1.26.4",
            "pandas==2.2.3",
            "fastapi==0.109.0",
            "uvicorn[standard]==0.27.0",
            "python-multipart==0.0.6",
            "pydantic==2.5.3",
            "pyngrok",
            "requests",
            "nest_asyncio",
        ]
        pkg_str = " ".join(packages)
        cmd = f"conda run -n {env_name} pip install {pkg_str}"
        run_command(cmd)


def verify_installation(env_name):
    """Verify the installation"""
    print("\n🔍 Verifying installation...")

    # Check Python
    result = run_command(
        f"conda run -n {env_name} python --version",
        capture_output=True
    )
    if result:
        print(f"   ✅ Python: {result.stdout.strip()}")

    # Check PyTorch and CUDA
    check_script = """
import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
"""
    result = run_command(
        f"conda run -n {env_name} python -c \"{check_script}\"",
        capture_output=True
    )
    if result and "PyTorch" in result.stdout:
        print("   ✅ PyTorch installation verified")
        for line in result.stdout.strip().split('\n'):
            print(f"      {line}")

    # Check WhisperX
    result = run_command(
        f"conda run -n {env_name} python -c \"import whisperx; print('WhisperX imported')\"",
        check=False, capture_output=True
    )
    if result and result.returncode == 0:
        print("   ✅ WhisperX imported successfully")
    else:
        print("   ⚠️  WhisperX import failed, will download on first run")


def print_activation_instructions(env_name):
    """Print instructions for activating the environment"""
    print("\n" + "=" * 60)
    print("✅ Installation Complete!")
    print("=" * 60)
    print("\n📋 Next Steps:")
    print(f"\n   1. Activate the environment:")
    print(f"      conda activate {env_name}")
    print(f"\n   2. Start the server:")
    print(f"      python whisperx_server.py")
    print(f"\n   3. Or use the unified notebook:")
    print(f"      jupyter notebook WhisperX_Cloud_Unified.ipynb")
    print(f"\n   4. For VideoLingo integration:")
    print(f"      - Set whisper.runtime = 'cloud' in config.yaml")
    print(f"      - Configure the cloud server URL")
    print("\n" + "=" * 60)


def main():
    """Main installation flow"""
    print(ASCII_LOGO)

    # Check conda
    if not check_conda():
        sys.exit(1)

    # Check GPU
    has_gpu = check_nvidia_gpu()

    # Get environment name
    env_name = input("\n📝 Enter environment name [whisperx-cloud]: ").strip()
    if not env_name:
        env_name = "whisperx-cloud"

    # Check if environment already exists
    result = run_command(
        f"conda env list | grep {env_name}",
        check=False, capture_output=True
    )
    if result and env_name in result.stdout:
        print(f"\n⚠️  Environment '{env_name}' already exists!")
        choice = input("   Remove and recreate? [y/N]: ").strip().lower()
        if choice == 'y':
            print(f"   Removing existing environment...")
            run_command(f"conda env remove -n {env_name} -y")
        else:
            print("   Using existing environment...")

    # Create environment
    create_conda_env(env_name, has_gpu)

    # Install PyTorch
    install_pytorch(env_name, has_gpu)

    # Install other dependencies
    install_dependencies(env_name)

    # Verify
    verify_installation(env_name)

    # Print instructions
    print_activation_instructions(env_name)


if __name__ == "__main__":
    main()
