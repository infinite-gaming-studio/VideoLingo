#!/usr/bin/env python3
"""
WhisperX Cloud API Server - Mamba/Conda Installation Script
Reference: VideoLingo/install.py

This script provides guided installation for the WhisperX Cloud server using mamba (preferred) or conda.
Mamba is 3-5x faster for dependency resolution and installation.

Usage:
    python install_conda.py

Requirements:
    - mamba (recommended) or conda
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


def check_mamba():
    """Check if mamba or conda is installed (prefer mamba)"""
    # 优先检查 mamba
    result = run_command("mamba --version", check=False, capture_output=True)
    if result and result.returncode == 0:
        print(f"✅ Mamba detected: {result.stdout.strip()}")
        return 'mamba'
    
    # 检查 conda 作为备选
    result = run_command("conda --version", check=False, capture_output=True)
    if result and result.returncode == 0:
        print(f"⚠️  Conda detected (recommend using Mamba for faster installation):")
        print(f"   {result.stdout.strip()}")
        print("\n   To install Mamba:")
        print("   conda install -c conda-forge mamba -n base -y")
        return 'conda'
    
    print("❌ Neither Mamba nor Conda found!")
    print("\n📥 Please install Miniforge (includes Mamba):")
    print("   wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh")
    print("   bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3")
    print("   export PATH=\"$HOME/miniforge3/bin:$PATH\"")
    print("\n   Or install Miniconda:")
    print("   https://docs.conda.io/en/latest/miniconda.html")
    print("\n   After installation, restart your terminal and run this script again.")
    return None


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


def create_env(cmd_type='mamba', env_name="whisperx-cloud", use_gpu=True):
    """Create environment using mamba or conda"""
    print(f"\n📦 Creating environment with {cmd_type}: {env_name}")

    # Determine Python version
    python_version = "3.10"

    # Create environment command (使用 mamba 或 conda)
    cmd_tool = 'mamba' if cmd_type == 'mamba' else 'conda'
    cmd = f"{cmd_tool} create -n {env_name} python={python_version} -y"

    print(f"   Python version: {python_version}")
    print(f"   Using: {cmd_tool}")
    run_command(cmd)

    return env_name


def install_pytorch(cmd_type='mamba', env_name="whisperx-cloud", use_gpu=True):
    """Install PyTorch with appropriate CUDA version using mamba or conda"""
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

    cmd_tool = 'mamba' if cmd_type == 'mamba' else 'conda'
    
    # Choose PyTorch installation command
    if use_gpu and cuda_version:
        # Use CUDA 11.8 for compatibility (works with CUDA 11.8 and 12.x)
        print(f"   Installing PyTorch with CUDA 11.8 support")
        print(f"   (Compatible with system CUDA {cuda_version})")
        print(f"   Using: {cmd_tool} (faster dependency resolution)")
        cmd = (
            f"conda run -n {env_name} {cmd_tool} install pytorch=2.0.0 "
            f"torchaudio=2.0.0 pytorch-cuda=11.8 -c pytorch -c nvidia -y"
        )
    else:
        print("   Installing CPU-only PyTorch")
        cmd = (
            f"conda run -n {env_name} {cmd_tool} install pytorch=2.0.0 "
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


def verify_installation(cmd_type='mamba', env_name="whisperx-cloud"):
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
    
    # Check mamba/conda
    print(f"   ✅ Package manager: {cmd_type}")


def print_activation_instructions(cmd_type='mamba', env_name="whisperx-cloud"):
    """Print instructions for activating the environment"""
    activate_cmd = 'conda' if cmd_type == 'conda' else 'conda'  # mamba 环境也用 conda activate
    
    print("\n" + "=" * 60)
    print("✅ Installation Complete!")
    print(f"   Package manager used: {cmd_type}")
    print("=" * 60)
    print("\n📋 Next Steps:")
    print(f"\n   1. Activate the environment:")
    print(f"      {activate_cmd} activate {env_name}")
    print(f"\n   2. Start the server:")
    print(f"      python whisperx_server.py")
    print(f"\n   3. Or use the unified notebook:")
    print(f"      jupyter notebook WhisperX_Cloud_Unified.ipynb")
    print(f"\n   4. For VideoLingo integration:")
    print(f"      - Set whisper.runtime = 'cloud' in config.yaml")
    print(f"      - Configure the cloud server URL")
    print(f"\n💡 Tip: Mamba is 3-5x faster than conda for package operations")
    print("=" * 60)


def main():
    """Main installation flow"""
    print(ASCII_LOGO)

    # Check mamba/conda
    cmd_type = check_mamba()
    if not cmd_type:
        sys.exit(1)

    # Check GPU
    has_gpu = check_nvidia_gpu()

    # Get environment name
    env_name = input("\n📝 Enter environment name [whisperx-cloud]: ").strip()
    if not env_name:
        env_name = "whisperx-cloud"

    # Check if environment already exists
    cmd_tool = 'mamba' if cmd_type == 'mamba' else 'conda'
    result = run_command(
        f"{cmd_tool} env list | grep {env_name}",
        check=False, capture_output=True
    )
    if result and env_name in result.stdout:
        print(f"\n⚠️  Environment '{env_name}' already exists!")
        choice = input("   Remove and recreate? [y/N]: ").strip().lower()
        if choice == 'y':
            print(f"   Removing existing environment...")
            run_command(f"{cmd_tool} env remove -n {env_name} -y")
        else:
            print("   Using existing environment...")

    # Create environment using mamba/conda
    create_env(cmd_type, env_name, has_gpu)

    # Install PyTorch
    install_pytorch(cmd_type, env_name, has_gpu)

    # Install other dependencies
    install_dependencies(env_name)

    # Verify
    verify_installation(cmd_type, env_name)

    # Print instructions
    print_activation_instructions(cmd_type, env_name)


if __name__ == "__main__":
    main()
