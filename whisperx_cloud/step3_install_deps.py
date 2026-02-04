#!/usr/bin/env python3
"""
Step 3: 安装 Conda 和依赖 (运维级版本)

特点：
- 结构化日志记录
- 磁盘/内存预检
- 网络重试机制
- 原子性安装（失败自动回滚）
- 详细进度报告
"""

import subprocess
import sys
import os
import socket
import requests
import shutil
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

# 配置
INSTALL_TIMEOUT = 1800  # 30分钟超时
MAX_RETRIES = 3
RETRY_DELAY = 5


class Logger:
    """结构化日志记录器"""
    def __init__(self, log_file: str = "install.log"):
        self.log_file = log_file
        self.start_time = time.time()
        
    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _elapsed(self) -> str:
        elapsed = time.time() - self.start_time
        return f"[{elapsed:.1f}s]"
    
    def log(self, level: str, message: str):
        """记录日志"""
        timestamp = self._timestamp()
        elapsed = self._elapsed()
        log_line = f"{timestamp} {elapsed} [{level}] {message}"
        
        # 写入文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
        
        # 输出到终端
        print(message)
    
    def info(self, msg: str):
        self.log("INFO", msg)
    
    def success(self, msg: str):
        self.log("SUCCESS", f"✅ {msg}")
    
    def warning(self, msg: str):
        self.log("WARNING", f"⚠️ {msg}")
    
    def error(self, msg: str):
        self.log("ERROR", f"❌ {msg}")
    
    def progress(self, msg: str):
        self.log("PROGRESS", f"📦 {msg}")
    
    def section(self, msg: str):
        print(f"\n{'='*60}")
        print(f"🚀 {msg}")
        print(f"{'='*60}\n")
        self.log("SECTION", msg)


# 全局日志器
logger = Logger()


def detect_server_environment():
    """检测当前运行的服务器环境"""
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
    
    logger.warning(f"Unknown environment (hostname: {hostname})")
    return 'unknown'


def check_disk_space(path: str, min_gb: float = 10.0) -> Tuple[bool, float]:
    """检查磁盘空间"""
    try:
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024**3)
        if free_gb < min_gb:
            logger.error(f"磁盘空间不足: {free_gb:.1f}GB < {min_gb}GB required")
            return False, free_gb
        logger.success(f"磁盘空间充足: {free_gb:.1f}GB")
        return True, free_gb
    except Exception as e:
        logger.error(f"无法检查磁盘空间: {e}")
        return False, 0


def check_network(timeout: int = 10) -> bool:
    """检查网络连接"""
    test_urls = [
        "https://repo.anaconda.com",
        "https://github.com",
        "https://pypi.org"
    ]
    for url in test_urls:
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                logger.success(f"网络连接正常: {url}")
                return True
        except:
            continue
    logger.error("网络连接异常，无法访问必要资源")
    return False


def run_with_retry(func, max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY, *args, **kwargs):
    """执行函数，失败时重试"""
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            return True, result
        except Exception as e:
            logger.warning(f"尝试 {attempt + 1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                logger.info(f"{delay}秒后重试...")
                time.sleep(delay)
            else:
                logger.error("所有重试均失败")
                return False, None
    return False, None


def get_conda_cmd():
    """获取 conda 命令路径，如果没有则安装"""
    # 检查标准 conda
    try:
        result = subprocess.run(['conda', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.success(f"Conda detected: {result.stdout.strip()}")
            return 'conda'
    except:
        pass
    
    # 检查用户目录 miniconda
    miniconda_conda = os.path.expanduser('~/miniconda3/bin/conda')
    if os.path.exists(miniconda_conda):
        os.environ['PATH'] = os.path.expanduser('~/miniconda3/bin:') + os.environ.get('PATH', '')
        result = subprocess.run([miniconda_conda, '--version'], capture_output=True, text=True, timeout=10)
        logger.success(f"Miniconda detected: {result.stdout.strip()}")
        return miniconda_conda
    
    # 安装 Miniconda
    logger.progress("Installing Miniconda...")
    install_path = os.path.expanduser("~/miniconda3")
    
    def _do_install():
        # 下载
        logger.info("Downloading Miniconda installer...")
        subprocess.run(
            ['wget', '-q', '--show-progress', 
             'https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh', 
             '-O', '/tmp/miniconda.sh'],
            check=True,
            timeout=120
        )
        
        # 安装
        logger.info("Running installer...")
        subprocess.run(
            ['bash', '/tmp/miniconda.sh', '-b', '-p', install_path],
            check=True,
            timeout=60
        )
        
        # 清理
        if os.path.exists('/tmp/miniconda.sh'):
            os.remove('/tmp/miniconda.sh')
        
        # 验证
        conda_bin = f"{install_path}/bin/conda"
        if not os.path.exists(conda_bin):
            raise RuntimeError("Conda 安装后未找到")
        
        # 更新 PATH
        os.environ['PATH'] = f"{install_path}/bin:" + os.environ.get('PATH', '')
        
        return conda_bin
    
    success, result = run_with_retry(_do_install, max_retries=2, delay=5)
    if success:
        logger.success("Miniconda installed")
        return result
    
    raise RuntimeError("Miniconda 安装失败")


def setup_environment_paths(server_env):
    """根据环境设置路径"""
    if server_env == 'colab':
        # 检查是否有 Google Drive 挂载
        if os.path.exists('/content/drive/MyDrive'):
            ENV_PREFIX = '/content/drive/MyDrive/conda-envs/whisperx-cloud'
            os.makedirs('/content/drive/MyDrive/conda-envs', exist_ok=True)
            os.environ['HF_HOME'] = '/content/drive/MyDrive/.cache/huggingface'
            os.environ['TORCH_HOME'] = '/content/drive/MyDrive/.cache/torch'
            os.environ['CONDA_PKGS_DIRS'] = '/content/drive/MyDrive/.cache/conda/pkgs'
            os.environ['PIP_CACHE_DIR'] = '/content/drive/MyDrive/.cache/pip'
            for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS'], os.environ['PIP_CACHE_DIR']]:
                os.makedirs(d, exist_ok=True)
            logger.info("Colab with Drive: Using persistent directory")
        else:
            ENV_PREFIX = '/content/conda-envs/whisperx-cloud'
            os.makedirs('/content/conda-envs', exist_ok=True)
            os.environ['HF_HOME'] = '/content/.cache/huggingface'
            os.environ['TORCH_HOME'] = '/content/.cache/torch'
            os.environ['CONDA_PKGS_DIRS'] = '/content/.cache/conda/pkgs'
            os.environ['PIP_CACHE_DIR'] = '/content/.cache/pip'
            for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS'], os.environ['PIP_CACHE_DIR']]:
                os.makedirs(d, exist_ok=True)
            logger.info("Colab without Drive: Using /content directory (non-persistent)")
    elif server_env == 'kaggle':
        ENV_PREFIX = '/kaggle/working/conda-envs/whisperx-cloud'
        os.makedirs('/kaggle/working/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/kaggle/working/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/kaggle/working/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/kaggle/working/.cache/conda/pkgs'
        os.environ['PIP_CACHE_DIR'] = '/kaggle/working/.cache/pip'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS'], os.environ['PIP_CACHE_DIR']]:
            os.makedirs(d, exist_ok=True)
        logger.info("Kaggle: Using persistent directory")
    elif server_env in ['sagemaker', 'aws']:
        ENV_PREFIX = '/home/ec2-user/conda-envs/whisperx-cloud'
        os.makedirs('/home/ec2-user/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/home/ec2-user/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/home/ec2-user/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/home/ec2-user/.cache/conda/pkgs'
        os.environ['PIP_CACHE_DIR'] = '/home/ec2-user/.cache/pip'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS'], os.environ['PIP_CACHE_DIR']]:
            os.makedirs(d, exist_ok=True)
        logger.info("AWS: Using EC2 user directory")
    elif server_env == 'azure':
        ENV_PREFIX = '/home/azureuser/conda-envs/whisperx-cloud'
        os.makedirs('/home/azureuser/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/home/azureuser/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/home/azureuser/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/home/azureuser/.cache/conda/pkgs'
        os.environ['PIP_CACHE_DIR'] = '/home/azureuser/.cache/pip'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS'], os.environ['PIP_CACHE_DIR']]:
            os.makedirs(d, exist_ok=True)
        logger.info("Azure: Using azureuser directory")
    elif server_env == 'gcp':
        ENV_PREFIX = '/home/jupyter/conda-envs/whisperx-cloud'
        os.makedirs('/home/jupyter/conda-envs', exist_ok=True)
        os.environ['HF_HOME'] = '/home/jupyter/.cache/huggingface'
        os.environ['TORCH_HOME'] = '/home/jupyter/.cache/torch'
        os.environ['CONDA_PKGS_DIRS'] = '/home/jupyter/.cache/conda/pkgs'
        os.environ['PIP_CACHE_DIR'] = '/home/jupyter/.cache/pip'
        for d in [os.environ['HF_HOME'], os.environ['TORCH_HOME'], os.environ['CONDA_PKGS_DIRS'], os.environ['PIP_CACHE_DIR']]:
            os.makedirs(d, exist_ok=True)
        logger.info("GCP: Using jupyter directory")
    else:
        ENV_PREFIX = None
        logger.info("Local/Unknown: Using default conda env location")
    
    return ENV_PREFIX


def create_environment_yml():
    """创建环境配置文件"""
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
    
    logger.success("Created environment.yml")


def cleanup_on_failure(env_prefix):
    """失败时清理"""
    logger.warning("Cleaning up on failure...")
    
    if env_prefix and os.path.exists(env_prefix):
        try:
            shutil.rmtree(env_prefix)
            logger.info(f"Removed: {env_prefix}")
        except Exception as e:
            logger.error(f"Failed to remove {env_prefix}: {e}")
    
    for tmp in ['/tmp/miniconda.sh', 'environment.yml']:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
                logger.info(f"Removed: {tmp}")
            except:
                pass


def verify_environment(env_prefix):
    """验证环境完整性"""
    logger.progress("Verifying environment...")
    
    checks = [
        ("环境目录", os.path.exists(env_prefix)),
        ("Python", os.path.exists(f"{env_prefix}/bin/python")),
        ("Conda", os.path.exists(f"{env_prefix}/bin/conda")),
    ]
    
    all_ok = True
    for name, ok in checks:
        if ok:
            logger.success(f"  {name}")
        else:
            logger.error(f"  {name}")
            all_ok = False
    
    if all_ok:
        # 显示目录内容
        try:
            result = subprocess.run(
                ['ls', '-la', env_prefix],
                capture_output=True,
                text=True
            )
            logger.info("Directory contents:")
            for line in result.stdout.strip().split('\n'):
                logger.info(f"  {line}")
        except Exception as e:
            logger.warning(f"Could not list directory: {e}")
        
        return True
    
    return False


def install_dependencies():
    """主安装流程"""
    logger.section("WhisperX Cloud Installation")
    start_time = time.time()
    
    ENV_PREFIX = None
    CONDA_CMD = None
    
    try:
        # 步骤 1: 检测环境
        logger.section("Step 1: Environment Detection")
        SERVER_ENV = detect_server_environment()
        logger.success(f"Detected environment: {SERVER_ENV.upper()}")
        
        ENV_PREFIX = setup_environment_paths(SERVER_ENV)
        
        # 步骤 2: 资源检查
        logger.section("Step 2: Resource Check")
        
        # 检查磁盘空间
        check_path = os.path.dirname(ENV_PREFIX) if ENV_PREFIX else '/tmp'
        ok, free_gb = check_disk_space(check_path, min_gb=15.0)
        if not ok:
            raise RuntimeError("Insufficient disk space")
        
        # 检查网络
        if not check_network():
            raise RuntimeError("Network check failed")
        
        # 步骤 3: 安装 Conda
        logger.section("Step 3: Conda Installation")
        CONDA_CMD = get_conda_cmd()
        
        # 接受 Anaconda ToS
        logger.info("Accepting Anaconda Terms of Service...")
        try:
            subprocess.run(
                [CONDA_CMD, 'tos', 'accept', '--override-channels', 
                 '--channel', 'https://repo.anaconda.com/pkgs/main'],
                capture_output=True, check=False, timeout=10
            )
            subprocess.run(
                [CONDA_CMD, 'tos', 'accept', '--override-channels', 
                 '--channel', 'https://repo.anaconda.com/pkgs/r'],
                capture_output=True, check=False, timeout=10
            )
            logger.success("ToS accepted")
        except Exception as e:
            logger.warning(f"ToS acceptance warning: {e}")
        
        # 步骤 4: 创建环境
        logger.section("Step 4: Environment Creation")
        create_environment_yml()
        
        # 检查是否已存在
        if ENV_PREFIX:
            env_exists = os.path.exists(ENV_PREFIX)
        else:
            result = subprocess.run(
                [CONDA_CMD, 'env', 'list'],
                capture_output=True, text=True, timeout=30
            )
            env_exists = 'whisperx-cloud' in result.stdout
        
        if env_exists:
            logger.warning("Environment already exists")
            # 在 Colab 中不交互，直接删除重建
            if SERVER_ENV in ['colab', 'kaggle']:
                logger.info("Removing existing environment...")
                if ENV_PREFIX:
                    shutil.rmtree(ENV_PREFIX, ignore_errors=True)
                else:
                    subprocess.run(
                        [CONDA_CMD, 'env', 'remove', '-n', 'whisperx-cloud', '-y'],
                        capture_output=True, timeout=60
                    )
            else:
                choice = input("Remove and recreate? [y/N]: ").strip().lower()
                if choice == 'y':
                    logger.info("Removing existing environment...")
                    if ENV_PREFIX:
                        shutil.rmtree(ENV_PREFIX, ignore_errors=True)
                    else:
                        subprocess.run(
                            [CONDA_CMD, 'env', 'remove', '-n', 'whisperx-cloud', '-y'],
                            capture_output=True, timeout=60
                        )
                else:
                    logger.info("Using existing environment")
                    # 跳过创建，直接验证
                    if verify_environment(ENV_PREFIX):
                        logger.success("Environment verified")
                    else:
                        raise RuntimeError("Environment verification failed")
                    
                    # 保存配置
                    CONDA_PYTHON = f"{ENV_PREFIX}/bin/python" if ENV_PREFIX else \
                        os.path.expanduser('~/miniconda3/envs/whisperx-cloud/bin/python')
                    with open('.conda_python_path', 'w') as f:
                        f.write(CONDA_PYTHON)
                    logger.success(f"Configuration saved: {CONDA_PYTHON}")
                    
                    elapsed = time.time() - start_time
                    logger.section(f"Installation Complete (using existing env) - {elapsed:.1f}s")
                    return True
        
        # 创建新环境
        logger.progress("Creating new environment (this may take 5-10 minutes)...")
        logger.info(f"Target path: {ENV_PREFIX or 'default conda envs'}")
        
        if ENV_PREFIX:
            # 带实时输出的创建
            process = subprocess.Popen(
                [CONDA_CMD, 'env', 'create', '-f', 'environment.yml', 
                 '--prefix', ENV_PREFIX, '--yes'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 实时输出
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(f"  {line}")
            
            process.wait(timeout=INSTALL_TIMEOUT)
            
            if process.returncode != 0:
                raise RuntimeError(f"Conda create failed with code {process.returncode}")
        else:
            # 使用默认位置
            result = subprocess.run(
                [CONDA_CMD, 'env', 'create', '-f', 'environment.yml', '--yes'],
                capture_output=True, text=True, timeout=INSTALL_TIMEOUT
            )
            if result.returncode != 0:
                logger.error(f"Error: {result.stderr}")
                raise RuntimeError("Conda create failed")
        
        logger.success("Environment created")
        
        # 验证环境
        if not verify_environment(ENV_PREFIX):
            raise RuntimeError("Environment verification failed")
        
        # 步骤 5: 保存配置
        logger.section("Step 5: Save Configuration")
        
        CONDA_PYTHON = f"{ENV_PREFIX}/bin/python" if ENV_PREFIX else \
            os.path.expanduser('~/miniconda3/envs/whisperx-cloud/bin/python')
        
        # 验证 Python 存在
        if not os.path.exists(CONDA_PYTHON):
            logger.error(f"Python not found at: {CONDA_PYTHON}")
            raise RuntimeError("Python interpreter not found")
        
        # 保存配置
        config = {
            'python_path': CONDA_PYTHON,
            'env_prefix': ENV_PREFIX,
            'server_env': SERVER_ENV,
            'timestamp': datetime.now().isoformat()
        }
        
        with open('.conda_python_path', 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.success(f"Configuration saved: CONDA_PYTHON={CONDA_PYTHON}")
        
        # 显示环境信息
        if SERVER_ENV == 'colab':
            logger.info(f"COLAB: Environment at {ENV_PREFIX}")
        elif SERVER_ENV == 'kaggle':
            logger.info(f"KAGGLE: Environment at {ENV_PREFIX}")
        elif SERVER_ENV != 'local':
            logger.info(f"{SERVER_ENV.upper()}: Environment at {ENV_PREFIX}")
        
        elapsed = time.time() - start_time
        logger.section(f"Installation Complete - {elapsed:.1f}s")
        logger.success("All steps completed successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"Installation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 清理
        cleanup_on_failure(ENV_PREFIX)
        
        elapsed = time.time() - start_time
        logger.section(f"Installation Failed - {elapsed:.1f}s")
        logger.info(f"Check log for details: {logger.log_file}")
        
        return False


if __name__ == "__main__":
    success = install_dependencies()
    sys.exit(0 if success else 1)
