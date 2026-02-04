#!/usr/bin/env python3
"""
Step 3: 安装 Conda 和依赖
本脚本会：
1. 检查并安装 Miniconda（如果未安装）
2. 使用 Conda 创建环境并安装依赖

依赖版本说明 (参考 VideoLingo 父项目):
- torch==2.0.0 - 与 VideoLingo 保持一致
- whisperx@git+...853 - 固定 commit 保证稳定性
- ctranslate2==4.4.0 - whisperX 依赖的推理引擎
- transformers==4.39.3 - HuggingFace 模型库
"""

import subprocess
import sys
import os


def get_conda_cmd():
    """获取 conda 命令路径，如果没有则安装"""
    # 检查标准 conda
    try:
        result = subprocess.run(['conda', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Conda detected: {result.stdout.strip()}")
            return 'conda'
    except:
        pass
    
    # 检查用户目录 miniconda
    miniconda_conda = os.path.expanduser('~/miniconda3/bin/conda')
    if os.path.exists(miniconda_conda):
        os.environ['PATH'] = os.path.expanduser('~/miniconda3/bin:') + os.environ.get('PATH', '')
        result = subprocess.run([miniconda_conda, '--version'], capture_output=True, text=True)
        print(f"✅ Miniconda detected: {result.stdout.strip()}")
        return miniconda_conda
    
    # 安装 Miniconda
    print("📥 Installing Miniconda...")
    subprocess.run(['wget', '-q', 'https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh', '-O', '/tmp/miniconda.sh'], check=True)
    subprocess.run(['bash', '/tmp/miniconda.sh', '-b', '-p', os.path.expanduser('~/miniconda3')], check=True)
    conda_cmd = os.path.expanduser('~/miniconda3/bin/conda')
    os.environ['PATH'] = os.path.expanduser('~/miniconda3/bin:') + os.environ.get('PATH', '')
    print("✅ Miniconda installed")
    return conda_cmd


def install_dependencies():
    """使用 Conda 安装依赖包"""
    
    CONDA_CMD = get_conda_cmd()
    
    print("\n📦 Installing dependencies with Conda...\n")
    
    # 检测平台 - 优先检测 Colab，再检测 Kaggle
    IN_COLAB = 'google.colab' in sys.modules
    IN_KAGGLE = os.path.exists('/kaggle')
    
    # Colab 持久化目录设置（Google Drive 挂载）
    if IN_COLAB:
        # 检查是否有 Google Drive 挂载
        if os.path.exists('/content/drive/MyDrive'):
            ENV_PREFIX = '/content/drive/MyDrive/conda-envs/whisperx-cloud'
            os.makedirs('/content/drive/MyDrive/conda-envs', exist_ok=True)
            os.environ['HF_HOME'] = '/content/drive/MyDrive/.cache/huggingface'
            os.environ['TORCH_HOME'] = '/content/drive/MyDrive/.cache/torch'
            os.environ['CONDA_PKGS_DIRS'] = '/content/drive/MyDrive/.cache/conda/pkgs'
            for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
                os.makedirs(d, exist_ok=True)
            print("📂 Colab with Drive: Using persistent directory")
        else:
            ENV_PREFIX = '/content/conda-envs/whisperx-cloud'
            os.makedirs('/content/conda-envs', exist_ok=True)
            os.environ['HF_HOME'] = '/content/.cache/huggingface'
            os.environ['TORCH_HOME'] = '/content/.cache/torch'
            os.environ['CONDA_PKGS_DIRS'] = '/content/.cache/conda/pkgs'
            for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
                os.makedirs(d, exist_ok=True)
            print("📂 Colab without Drive: Using /content directory (non-persistent)")
    elif IN_KAGGLE:
        ENV_PREFIX = '/kaggle/working/conda-envs/whisperx-cloud'
        os.makedirs('/kaggle/working/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/kaggle/working/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/kaggle/working/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/kaggle/working/.cache/conda/pkgs'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
            os.makedirs(d, exist_ok=True)
        print("📂 Kaggle: Using persistent directory")
    else:
        ENV_PREFIX = None
        print("📂 Local: Using default conda env location")
    
    # 创建环境文件
    environment_yml = '''name: whisperx-cloud
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
    
    with open('environment.yml', 'w') as f:
        f.write(environment_yml)
    print("📝 Created environment.yml")
    
    # 检查环境是否已存在
    if ENV_PREFIX:
        env_exists = os.path.exists(ENV_PREFIX)
    else:
        result = subprocess.run([CONDA_CMD, 'env', 'list'], capture_output=True, text=True)
        env_exists = 'whisperx-cloud' in result.stdout
    
    # 创建或更新环境
    if env_exists:
        print("\n🔄 Environment exists, updating...")
        if ENV_PREFIX:
            subprocess.run([CONDA_CMD, 'env', 'update', '-f', 'environment.yml', '--prefix', ENV_PREFIX, '--yes'])
        else:
            subprocess.run([CONDA_CMD, 'env', 'update', '-f', 'environment.yml', '-n', 'whisperx-cloud', '--yes'])
    else:
        print("\n🆕 Creating new environment...")
        if ENV_PREFIX:
            subprocess.run([CONDA_CMD, 'env', 'create', '-f', 'environment.yml', '--prefix', ENV_PREFIX, '--yes'])
        else:
            subprocess.run([CONDA_CMD, 'env', 'create', '-f', 'environment.yml', '--yes'])
    
    print("\n✅ Conda environment setup complete!")
    
    # 获取 conda 环境的 Python 路径
    if ENV_PREFIX:
        CONDA_PYTHON = f"{ENV_PREFIX}/bin/python"
    else:
        CONDA_PYTHON = os.path.expanduser('~/miniconda3/envs/whisperx-cloud/bin/python')
    
    # 保存配置供后续步骤使用
    with open('.conda_python_path', 'w') as f:
        f.write(CONDA_PYTHON)
    
    print(f"\n📌 Conda Python path saved: {CONDA_PYTHON}")
    
    if IN_COLAB:
        print(f"\n📌 COLAB: Environment at {ENV_PREFIX}")
    elif IN_KAGGLE:
        print(f"\n📌 KAGGLE: Environment at {ENV_PREFIX}")
    
    return True


if __name__ == "__main__":
    install_dependencies()
