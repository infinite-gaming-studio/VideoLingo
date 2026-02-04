#!/usr/bin/env python3
"""
Step 3: 安装依赖 (强制使用 Conda)
本脚本强制使用 Conda 进行安装，以获得更好的环境隔离和 CUDA 依赖管理。

依赖版本说明 (参考 VideoLingo 父项目):
- torch==2.0.0 - 与 VideoLingo 保持一致
- whisperx@git+...853 - 固定 commit 保证稳定性
- ctranslate2==4.4.0 - whisperX 依赖的推理引擎
- transformers==4.39.3 - HuggingFace 模型库
"""

import subprocess
import sys
import os


def check_conda():
    """检查 Conda 是否可用"""
    try:
        result = subprocess.run(['conda', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Conda detected: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    return False


def install_dependencies():
    """使用 Conda 安装依赖包"""
    
    if not check_conda():
        print("❌ ERROR: Conda is not installed or not available in PATH!")
        print("\n请按以下步骤安装 Conda:")
        print("1. 安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html")
        print("2. 或使用 Anaconda: https://www.anaconda.com/download")
        print("3. 重新启动 Notebook 并确保 Conda 在 PATH 中")
        raise RuntimeError("Conda is required but not found")
    
    print("\n📦 Installing dependencies with Conda...\n")
    
    # 检测平台
    IN_KAGGLE = os.path.exists('/kaggle')
    
    # Kaggle 持久化目录设置 (Environment + Model Cache)
    if IN_KAGGLE:
        # Kaggle: 使用持久化目录保存环境和模型缓存
        ENV_PREFIX = '/kaggle/working/conda-envs/whisperx-cloud'
        os.makedirs('/kaggle/working/conda-envs', exist_ok=True)
        # 设置 HuggingFace 缓存目录到持久化区域（避免每次重启重新下载模型）
        os.environ['HF_HOME'] = '/kaggle/working/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/kaggle/working/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/kaggle/working/.cache/conda/pkgs'
        os.makedirs(os.environ['HF_HOME'], exist_ok=True)
        os.makedirs(os.environ['TORCH_HOME'], exist_ok=True)
        os.makedirs(os.environ['CONDA_PKGS_DIRS'], exist_ok=True)
        print("📂 Kaggle detected: Using persistent directory")
        print(f"   Environment path: {ENV_PREFIX}")
        print(f"   HF Cache: {os.environ['HF_HOME']}")
        print(f"   Torch Cache: {os.environ['TORCH_HOME']}")
    else:
        # 本地或其他环境：使用默认命名环境
        ENV_PREFIX = None
        print("📂 Local environment: Using default conda env location")
    
    # 创建 conda 环境文件内容
    environment_yml = '''
name: whisperx-cloud
channels:
  - pytorch
  - nvidia
  - conda-forge
  - defaults
dependencies:
  - python=3.10
  - pytorch=2.0.0
  - torchaudio=2.0.0
  - pytorch-cuda=11.8
  - pip
  - pip:
    - fastapi==0.109.0
    - uvicorn[standard]==0.27.0
    - python-multipart==0.0.6
    - pydantic==2.5.3
    - requests
    - pyngrok
    - whisperx@git+https://github.com/m-bain/whisperx.git@7307306a9d8dd0d261e588cc933322454f853853
'''
    
    # 写入环境文件
    with open('environment.yml', 'w') as f:
        f.write(environment_yml)
    
    print("\n📝 Created environment.yml")
    
    # 检查环境是否已存在
    if ENV_PREFIX:
        # Kaggle: 检查前缀路径
        env_exists = os.path.exists(ENV_PREFIX)
    else:
        # 本地: 检查命名环境
        result = subprocess.run(['conda', 'env', 'list'], capture_output=True, text=True)
        env_exists = 'whisperx-cloud' in result.stdout
    
    if env_exists:
        print("\n🔄 Environment 'whisperx-cloud' already exists, updating...")
        if ENV_PREFIX:
            subprocess.check_call(['conda', 'env', 'update', '-f', 'environment.yml', '--prefix', ENV_PREFIX, '--yes'])
        else:
            subprocess.check_call(['conda', 'env', 'update', '-f', 'environment.yml', '-n', 'whisperx-cloud', '--yes'])
    else:
        print("\n🆕 Creating new conda environment 'whisperx-cloud'...")
        if ENV_PREFIX:
            subprocess.check_call(['conda', 'env', 'create', '-f', 'environment.yml', '--prefix', ENV_PREFIX, '--yes'])
        else:
            subprocess.check_call(['conda', 'env', 'create', '-f', 'environment.yml', '--yes'])
    
    print("\n✅ Conda environment setup complete!")
    
    if IN_KAGGLE:
        print(f"\n📌 KAGGLE: Environment is persisted at: {ENV_PREFIX}")
        print("   To activate in a new session:")
        print(f"   conda activate {ENV_PREFIX}")
        print("\n   Or use the conda run command:")
        print(f"   conda run -p {ENV_PREFIX} python your_script.py")
    else:
        print("\n📌 IMPORTANT: 请手动激活环境后重新运行 Notebook:")
        print("   1. 关闭当前 Notebook")
        print("   2. 在终端执行: conda activate whisperx-cloud")
        print("   3. 在该环境中重新启动 Jupyter Notebook")
        print("\n   或者使用 nb_conda_kernels 在 Notebook 中选择环境")
    
    # 可选的 speaker diarization
    try:
        from config import ENABLE_DIARIZATION
        if ENABLE_DIARIZATION:
            print("\n📦 Note: Speaker diarization requires pyannote.audio")
            print("   Install with: pip install pyannote.audio==3.1.1")
    except ImportError:
        pass
    
    print("\n⚠️  安装完成后，请确保使用 'whisperx-cloud' 环境运行此 Notebook")
    
    return True


if __name__ == "__main__":
    install_dependencies()
