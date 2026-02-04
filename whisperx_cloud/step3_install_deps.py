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
import socket
import requests


def detect_server_environment():
    """
    检测当前运行的服务器环境
    返回: 'colab', 'kaggle', 'sagemaker', 'azure', 'gcp', 'aws', 'local', 'unknown'
    """
    hostname = socket.gethostname().lower()
    
    # 1. Colab 检测 (多种方式)
    if (
        'google.colab' in sys.modules or
        os.path.exists('/content') or
        'COLAB_GPU' in os.environ or
        'COLAB_TPU_ADDR' in os.environ or
        'colab' in hostname
    ):
        return 'colab'
    
    # 2. Kaggle 检测
    if (
        os.path.exists('/kaggle') or
        'KAGGLE_KERNEL_RUN_TYPE' in os.environ or
        'kaggle' in hostname
    ):
        return 'kaggle'
    
    # 3. AWS SageMaker 检测
    if (
        'SAGEMAKER_INTERNAL_IMAGE_URI' in os.environ or
        'SM_MODEL_DIR' in os.environ or
        'sagemaker' in hostname or
        'aws' in hostname
    ):
        return 'sagemaker'
    
    # 4. Azure ML 检测
    if (
        'AZUREML_ARM_SUBSCRIPTION' in os.environ or
        'AML_APP_ROOT' in os.environ or
        'azure' in hostname or
        'aml' in hostname
    ):
        return 'azure'
    
    # 5. GCP Vertex AI / Compute Engine 检测
    # 尝试访问 GCP 元数据服务
    try:
        response = requests.get(
            'http://metadata.google.internal/computeMetadata/v1/instance/',
            headers={'Metadata-Flavor': 'Google'},
            timeout=1
        )
        if response.status_code == 200:
            return 'gcp'
    except:
        pass
    
    # 6. AWS EC2 检测
    # 尝试访问 EC2 元数据服务
    try:
        response = requests.get(
            'http://169.254.169.254/latest/meta-data/',
            timeout=1
        )
        if response.status_code == 200:
            return 'aws'
    except:
        pass
    
    # 7. 本地开发环境
    if (
        hostname in ['localhost', '127.0.0.1', ''] or
        hostname.endswith('.local') or
        os.path.exists('/Users')  # macOS
    ):
        return 'local'
    
    print(f"⚠️ Unknown environment (hostname: {hostname})")
    return 'unknown'


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
    
    # 接受 Anaconda ToS（避免交互式确认）
    print("\n📋 Accepting Anaconda Terms of Service...")
    try:
        subprocess.run([CONDA_CMD, 'tos', 'accept', '--override-channels', '--channel', 'https://repo.anaconda.com/pkgs/main'], 
                      capture_output=True, check=False)
        subprocess.run([CONDA_CMD, 'tos', 'accept', '--override-channels', '--channel', 'https://repo.anaconda.com/pkgs/r'],
                      capture_output=True, check=False)
        print("✅ ToS accepted")
    except:
        pass
    
    print("\n📦 Installing dependencies with Conda...\n")
    
    # 检测服务器环境
    SERVER_ENV = detect_server_environment()
    print(f"🔍 Detected environment: {SERVER_ENV.upper()}")
    
    # 根据环境设置路径
    if SERVER_ENV == 'colab':
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
    elif SERVER_ENV == 'kaggle':
        ENV_PREFIX = '/kaggle/working/conda-envs/whisperx-cloud'
        os.makedirs('/kaggle/working/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/kaggle/working/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/kaggle/working/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/kaggle/working/.cache/conda/pkgs'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
            os.makedirs(d, exist_ok=True)
        print("📂 Kaggle: Using persistent directory")
    elif SERVER_ENV in ['sagemaker', 'aws']:
        ENV_PREFIX = '/home/ec2-user/conda-envs/whisperx-cloud'
        os.makedirs('/home/ec2-user/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/home/ec2-user/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/home/ec2-user/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/home/ec2-user/.cache/conda/pkgs'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
            os.makedirs(d, exist_ok=True)
        print("📂 AWS: Using EC2 user directory")
    elif SERVER_ENV == 'azure':
        ENV_PREFIX = '/home/azureuser/conda-envs/whisperx-cloud'
        os.makedirs('/home/azureuser/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/home/azureuser/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/home/azureuser/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/home/azureuser/.cache/conda/pkgs'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
            os.makedirs(d, exist_ok=True)
        print("📂 Azure: Using azureuser directory")
    elif SERVER_ENV == 'gcp':
        ENV_PREFIX = '/home/jupyter/conda-envs/whisperx-cloud'
        os.makedirs('/home/jupyter/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/home/jupyter/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/home/jupyter/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/home/jupyter/.cache/conda/pkgs'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS']]:
            os.makedirs(d, exist_ok=True)
        print("📂 GCP: Using jupyter directory")
    else:
        ENV_PREFIX = None
        print("📂 Local/Unknown: Using default conda env location")
    
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
    try:
        if env_exists:
            print("\n🔄 Environment exists, updating...")
            if ENV_PREFIX:
                result = subprocess.run([CONDA_CMD, 'env', 'update', '-f', 'environment.yml', '--prefix', ENV_PREFIX, '--yes'], 
                                      capture_output=True, text=True)
            else:
                result = subprocess.run([CONDA_CMD, 'env', 'update', '-f', 'environment.yml', '-n', 'whisperx-cloud', '--yes'],
                                      capture_output=True, text=True)
        else:
            print("\n🆕 Creating new environment...")
            if ENV_PREFIX:
                result = subprocess.run([CONDA_CMD, 'env', 'create', '-f', 'environment.yml', '--prefix', ENV_PREFIX, '--yes'],
                                      capture_output=True, text=True)
            else:
                result = subprocess.run([CONDA_CMD, 'env', 'create', '-f', 'environment.yml', '--yes'],
                                      capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"\n❌ Conda environment creation failed!")
            print(f"Error output: {result.stderr}")
            print(f"Standard output: {result.stdout}")
            return False
            
        print("\n✅ Conda environment setup complete!")
        
        # 获取 conda 环境的 Python 路径
        if ENV_PREFIX:
            CONDA_PYTHON = f"{ENV_PREFIX}/bin/python"
        else:
            CONDA_PYTHON = os.path.expanduser('~/miniconda3/envs/whisperx-cloud/bin/python')
        
        # 验证 Python 解释器是否存在
        if not os.path.exists(CONDA_PYTHON):
            print(f"\n❌ Python interpreter not found at: {CONDA_PYTHON}")
            print("Checking environment directory contents...")
            if ENV_PREFIX and os.path.exists(ENV_PREFIX):
                import subprocess as sp
                ls_result = sp.run(['ls', '-la', ENV_PREFIX], capture_output=True, text=True)
                print(ls_result.stdout)
            return False
        
        # 保存配置供后续步骤使用
        with open('.conda_python_path', 'w') as f:
            f.write(CONDA_PYTHON)
        
        print(f"\n📌 Conda Python path saved: {CONDA_PYTHON}")
        
        if SERVER_ENV == 'colab':
            print(f"\n📌 COLAB: Environment at {ENV_PREFIX}")
        elif SERVER_ENV == 'kaggle':
            print(f"\n📌 KAGGLE: Environment at {ENV_PREFIX}")
        elif SERVER_ENV != 'local':
            print(f"\n📌 {SERVER_ENV.upper()}: Environment at {ENV_PREFIX}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during environment setup: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    install_dependencies()
