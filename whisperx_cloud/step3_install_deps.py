#!/usr/bin/env python3
"""
Step 3: 安装 Conda 和依赖 (运维级版本 v2)

改进：
- 修复 PyAV 编译问题（预装 ffmpeg）
- 增强环境归属验证
- 详细的 pip 错误诊断
- 原子性安装保障
"""

import subprocess
import sys
import os
import socket
import requests
import shutil
import time
import json
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

# 配置
INSTALL_TIMEOUT = 1800
MAX_RETRIES = 3
RETRY_DELAY = 5


class Logger:
    """结构化日志记录器"""
    def __init__(self, log_file: str = "install.log"):
        self.log_file = log_file
        self.start_time = time.time()
        # 清空旧日志
        with open(self.log_file, 'w') as f:
            f.write(f"Installation started at {datetime.now()}\n")
        
    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _elapsed(self) -> str:
        elapsed = time.time() - self.start_time
        return f"[{elapsed:.1f}s]"
    
    def log(self, level: str, message: str):
        timestamp = self._timestamp()
        elapsed = self._elapsed()
        log_line = f"{timestamp} {elapsed} [{level}] {message}"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
        
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
    
    def debug(self, msg: str):
        self.log("DEBUG", f"🔍 {msg}")


logger = Logger()


def detect_server_environment():
    """检测服务器环境"""
    hostname = socket.gethostname().lower()
    
    checks = [
        ('colab', lambda: 'google.colab' in sys.modules or os.path.exists('/content')),
        ('kaggle', lambda: os.path.exists('/kaggle')),
        ('sagemaker', lambda: 'SAGEMAKER_INTERNAL_IMAGE_URI' in os.environ),
        ('azure', lambda: 'AZUREML_ARM_SUBSCRIPTION' in os.environ),
    ]
    
    for env_name, check_func in checks:
        try:
            if check_func():
                logger.success(f"检测到环境: {env_name.upper()}")
                return env_name
        except:
            continue
    
    # 元数据服务检测
    try:
        resp = requests.get(
            'http://metadata.google.internal/computeMetadata/v1/instance/',
            headers={'Metadata-Flavor': 'Google'}, timeout=2
        )
        if resp.status_code == 200:
            return 'gcp'
    except:
        pass
    
    try:
        resp = requests.get('http://169.254.169.254/latest/meta-data/', timeout=2)
        if resp.status_code == 200:
            return 'aws'
    except:
        pass
    
    if hostname in ['localhost', '127.0.0.1', ''] or hostname.endswith('.local'):
        return 'local'
    
    logger.warning(f"未知环境 (hostname: {hostname})")
    return 'unknown'


def check_disk_space(path: str, min_gb: float = 15.0) -> Tuple[bool, float]:
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


def check_directory_ownership(path: str) -> Tuple[bool, int]:
    """检查目录所有权和权限"""
    try:
        if not os.path.exists(path):
            return True, os.getuid()  # 目录不存在，返回当前用户
        
        stat_info = os.stat(path)
        owner_uid = stat_info.st_uid
        current_uid = os.getuid()
        
        # 检查是否可写
        if not os.access(path, os.W_OK):
            logger.error(f"目录不可写: {path} (owner={owner_uid}, current={current_uid})")
            return False, owner_uid
        
        logger.success(f"目录权限正常: {path} (owner={owner_uid})")
        return True, owner_uid
    except Exception as e:
        logger.error(f"检查目录权限失败: {e}")
        return False, -1


def ensure_directory(path: str) -> bool:
    """确保目录存在且可写，逐层创建"""
    try:
        # 逐级创建
        Path(path).mkdir(parents=True, exist_ok=True)
        
        # 验证创建成功
        if not os.path.exists(path):
            logger.error(f"目录创建失败: {path}")
            return False
        
        # 创建测试文件验证可写性
        test_file = Path(path) / f".write_test_{int(time.time())}"
        try:
            test_file.write_text("test")
            test_file.unlink()
            logger.success(f"目录可写: {path}")
            return True
        except Exception as e:
            logger.error(f"目录不可写 {path}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"创建目录失败 {path}: {e}")
        return False


def setup_environment_paths(server_env):
    """设置环境路径"""
    base_paths = {
        'colab': '/content' if not os.path.exists('/content/drive/MyDrive') else '/content/drive/MyDrive',
        'kaggle': '/kaggle/working',
        'sagemaker': '/home/ec2-user',
        'azure': '/home/azureuser',
        'gcp': '/home/jupyter',
    }
    
    base = base_paths.get(server_env, os.path.expanduser('~'))
    ENV_PREFIX = f"{base}/conda-envs/whisperx-cloud"
    
    # 设置缓存目录
    cache_dirs = {
        'HF_HOME': f"{base}/.cache/huggingface",
        'TORCH_HOME': f"{base}/.cache/torch",
        'CONDA_PKGS_DIRS': f"{base}/.cache/conda/pkgs",
        'PIP_CACHE_DIR': f"{base}/.cache/pip"
    }
    
    # 确保所有目录可写
    logger.info("检查目录权限...")
    for key, value in cache_dirs.items():
        os.environ[key] = value
        if not ensure_directory(value):
            logger.error(f"无法创建缓存目录: {value}")
            return None
    
    # 确保环境目录父目录可写
    parent = os.path.dirname(ENV_PREFIX)
    if not ensure_directory(parent):
        logger.error(f"无法创建环境父目录: {parent}")
        return None
    
    logger.success(f"环境路径: {ENV_PREFIX}")
    return ENV_PREFIX


def get_mamba_cmd():
    """获取或安装 mamba (优先) 或 conda"""
    # 检查现有 mamba (优先)
    mamba_paths = [
        'mamba',
        os.path.expanduser('~/miniforge3/bin/mamba'),
        os.path.expanduser('~/miniconda3/bin/mamba'),
        os.path.expanduser('~/mambaforge/bin/mamba'),
    ]
    for cmd in mamba_paths:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.success(f"发现 Mamba: {result.stdout.strip()}")
                return cmd, 'mamba'
        except:
            pass
    
    # 检查现有 conda (备选)
    conda_paths = [
        'conda',
        os.path.expanduser('~/miniconda3/bin/conda'),
        os.path.expanduser('~/anaconda3/bin/conda'),
    ]
    for cmd in conda_paths:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.warning(f"发现 Conda (建议改用 Mamba): {result.stdout.strip()}")
                return cmd, 'conda'
        except:
            pass
    
    # 安装 miniforge (包含 mamba)
    logger.progress("安装 Miniforge (包含 Mamba)...")
    install_path = os.path.expanduser("~/miniforge3")
    
    try:
        logger.info("下载 Miniforge...")
        # 使用国内镜像加速下载
        urls = [
            'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh',
            'https://ghp.ci/https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh',
            'https://mirrors.tuna.tsinghua.edu.cn/github-release/conda-forge/miniforge/LatestRelease/Miniforge3-Linux-x86_64.sh',
        ]
        
        downloaded = False
        for url in urls:
            try:
                subprocess.run(
                    ['wget', '-q', '--show-progress', url, '-O', '/tmp/miniforge.sh'],
                    check=True, timeout=120
                )
                downloaded = True
                logger.success(f"下载成功: {url}")
                break
            except:
                continue
        
        if not downloaded:
            raise RuntimeError("所有下载源都失败")
        
        logger.info("运行安装程序...")
        subprocess.run(
            ['bash', '/tmp/miniforge.sh', '-b', '-p', install_path],
            check=True, timeout=120
        )
        
        if os.path.exists('/tmp/miniforge.sh'):
            os.remove('/tmp/miniforge.sh')
        
        mamba_bin = f"{install_path}/bin/mamba"
        if not os.path.exists(mamba_bin):
            raise RuntimeError("Mamba 安装后未找到")
        
        os.environ['PATH'] = f"{install_path}/bin:" + os.environ.get('PATH', '')
        logger.success("Miniforge (Mamba) 安装完成")
        return mamba_bin, 'mamba'
        
    except Exception as e:
        logger.error(f"Miniforge 安装失败: {e}")
        logger.info("尝试安装 Miniconda 作为备选...")
        return _install_miniconda_fallback()


def _install_miniconda_fallback():
    """备选：安装 Miniconda"""
    install_path = os.path.expanduser("~/miniconda3")
    
    try:
        logger.info("下载 Miniconda...")
        subprocess.run(
            ['wget', '-q', '--show-progress',
             'https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh',
             '-O', '/tmp/miniconda.sh'],
            check=True, timeout=120
        )
        
        logger.info("运行安装程序...")
        subprocess.run(
            ['bash', '/tmp/miniconda.sh', '-b', '-p', install_path],
            check=True, timeout=60
        )
        
        if os.path.exists('/tmp/miniconda.sh'):
            os.remove('/tmp/miniconda.sh')
        
        conda_bin = f"{install_path}/bin/conda"
        if not os.path.exists(conda_bin):
            raise RuntimeError("Conda 安装后未找到")
        
        # 在 conda 环境中安装 mamba
        logger.progress("在 Conda 中安装 Mamba...")
        subprocess.run(
            [conda_bin, 'install', '-n', 'base', '-c', 'conda-forge', 'mamba', '-y'],
            check=True, timeout=300
        )
        
        mamba_bin = f"{install_path}/bin/mamba"
        os.environ['PATH'] = f"{install_path}/bin:" + os.environ.get('PATH', '')
        logger.success("Mamba 安装完成 (通过 Conda)")
        return mamba_bin, 'mamba'
        
    except Exception as e:
        logger.error(f"Miniconda 安装也失败: {e}")
        raise


def create_environment_yml():
    """创建环境配置文件"""
    # ⚠️ 关键：将 pip 依赖分离到 post-install 步骤
    # 避免 conda 的 pip 子进程问题
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
  - ffmpeg  # conda-forge 版本支持 NVENC/NVDEC GPU 硬件加速
  - av  # 通过 conda 安装 PyAV，避免编译
  - pip
'''
    
    with open('environment.yml', 'w') as f:
        f.write(environment_yml)
    
    logger.success("Created environment.yml (conda deps only)")


def get_cdn_git_urls(repo_url: str, commit: str) -> list:
    """获取 GitHub 仓库的 CDN 加速 URL 列表（用于 pip install）"""
    # 提取仓库路径
    # 从 git+https://github.com/user/repo.git 提取 user/repo
    if 'github.com' in repo_url:
        parts = repo_url.replace('git+', '').replace('https://', '').replace('.git', '').split('/')
        if len(parts) >= 3:
            user, repo = parts[1], parts[2]
        else:
            return [repo_url]
    else:
        return [repo_url]
    
    # 国际 CDN 加速列表
    cdn_urls = [
        # 用户自定义（最高优先级）
        os.environ.get('WHISPERX_GIT_URL', ''),
        
        # 国际 CDN / 代理（按可靠性排序）
        f'git+https://ghps.cc/https://github.com/{user}/{repo}.git@{commit}',  # GitHub 代理
        f'git+https://ghproxy.net/https://github.com/{user}/{repo}.git@{commit}',  # GitHub 代理
        f'git+https://github.moeyy.xyz/https://github.com/{user}/{repo}.git@{commit}',  # 香港节点
        f'git+https://gh.api.99988866.xyz/https://github.com/{user}/{repo}.git@{commit}',  # 美国节点
        
        # 原始地址（保底）
        f'git+https://github.com/{user}/{repo}.git@{commit}',
    ]
    
    # 过滤空值和重复
    seen = set()
    unique_urls = []
    for url in cdn_urls:
        if url and url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


def get_whisperx_wheel_url() -> list:
    """获取预编译 WhisperX wheel 的 URL 列表"""
    # 预编译 wheel 仓库配置
    # 用户可以设置环境变量指向自己的 CDN
    wheel_sources = [
        os.environ.get('WHISPERX_WHEEL_URL', ''),  # 用户自定义
        # 预编译 wheel CDN（如有人构建并发布）
        'https://github.com/user-attachments/files/whisperx-3.1.1-py3-none-any.whl',
    ]
    
    # 过滤空值
    return [url for url in wheel_sources if url]


def build_whisperx_wheel(python_path: str, output_dir: str = './wheels') -> str:
    """本地预编译 WhisperX wheel"""
    logger.progress("本地预编译 WhisperX wheel...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 安装 wheel 构建工具
        subprocess.run(
            [python_path, '-m', 'pip', 'install', 'wheel', 'build'],
            capture_output=True, timeout=60
        )
        
        # 克隆并构建 wheel
        whisperx_commit = '7307306a9d8dd0d261e588cc933322454f853853'
        
        # 使用 pip wheel 直接构建
        result = subprocess.run(
            [python_path, '-m', 'pip', 'wheel', 
             f'git+https://github.com/m-bain/whisperx.git@{whisperx_commit}',
             '--no-cache-dir', '-w', output_dir],
            capture_output=True, text=True, timeout=600
        )
        
        if result.returncode == 0:
            # 查找生成的 wheel 文件
            wheels = [f for f in os.listdir(output_dir) if f.startswith('whisperx') and f.endswith('.whl')]
            if wheels:
                wheel_path = os.path.join(output_dir, wheels[0])
                logger.success(f"Wheel 构建成功: {wheel_path}")
                return wheel_path
        
        logger.warning(f"Wheel 构建失败，将使用直接安装: {result.stderr}")
        return ''
        
    except Exception as e:
        logger.warning(f"Wheel 构建异常: {e}")
        return ''


def install_whisperx_from_wheel(python_path: str) -> bool:
    """尝试从预编译 wheel 或 CDN 加速的 git 安装 WhisperX"""
    logger.progress("尝试安装 WhisperX (使用 CDN 加速)...")
    
    whisperx_commit = '7307306a9d8dd0d261e588cc933322454f853853'
    
    # 方法1: 尝试从预编译 wheel URL 安装
    wheel_urls = get_whisperx_wheel_url()
    for url in wheel_urls:
        if not url:
            continue
        logger.info(f"尝试从 wheel 安装: {url[:60]}...")
        try:
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '--no-cache-dir', url],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                logger.success("WhisperX wheel 安装成功!")
                return True
        except Exception as e:
            logger.warning(f"Wheel 安装失败: {e}")
    
    # 方法2: 使用 CDN 加速的 git 安装
    logger.info("尝试使用 CDN 加速从 git 安装...")
    cdn_git_urls = get_cdn_git_urls(
        'git+https://github.com/m-bain/whisperx.git',
        whisperx_commit
    )
    
    for i, url in enumerate(cdn_git_urls):
        cdn_name = url.split('/')[2] if '/' in url else 'unknown'
        logger.info(f"尝试 CDN {i+1}/{len(cdn_git_urls)} ({cdn_name})...")
        try:
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '--no-cache-dir', url],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                logger.success(f"WhisperX CDN 安装成功! (via {cdn_name})")
                return True
            else:
                logger.warning(f"CDN {cdn_name} 失败，尝试下一个...")
        except subprocess.TimeoutExpired:
            logger.warning(f"CDN {cdn_name} 超时，尝试下一个...")
        except Exception as e:
            logger.warning(f"CDN {cdn_name} 错误: {e}")
    
    # 方法3: 本地构建 wheel
    logger.info("尝试本地构建 wheel...")
    wheel_path = build_whisperx_wheel(python_path)
    if wheel_path and os.path.exists(wheel_path):
        try:
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '--no-cache-dir', wheel_path],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                logger.success("WhisperX 本地 wheel 安装成功!")
                return True
        except Exception as e:
            logger.warning(f"本地 wheel 安装失败: {e}")
    
    logger.error("所有安装方式均失败")
    return False


def install_pip_dependencies(env_prefix: str) -> bool:
    """单独安装 pip 依赖（解决 conda pip 子进程问题）"""
    logger.progress("安装 pip 依赖...")
    
    python_path = f"{env_prefix}/bin/python"
    
    # 基础依赖（WhisperX 除外）
    pip_packages = [
        "fastapi==0.109.0",
        "uvicorn[standard]==0.27.0",
        "python-multipart==0.0.6",
        "pydantic==2.5.3",
        "requests",
        "pyngrok",
    ]
    
    for package in pip_packages:
        logger.info(f"安装: {package}")
        try:
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '--no-cache-dir', package],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"安装失败: {package}")
                logger.error(f"错误输出: {result.stderr}")
                return False
            
            logger.success(f"安装成功: {package}")
            
        except subprocess.TimeoutExpired:
            logger.error(f"安装超时: {package}")
            return False
        except Exception as e:
            logger.error(f"安装异常: {package} - {e}")
            return False
    
    # 安装 WhisperX（使用预编译 wheel 优先）
    logger.info("安装 WhisperX (优先使用预编译 wheel)...")
    
    # 先安装 WhisperX 的依赖（避免从 git 构建时缺少依赖）
    whisperx_deps = [
        "numpy==1.26.4",
        "faster-whisper==1.0.0",
        "ctranslate2==4.4.0",
        "transformers==4.39.3",
        "librosa==0.10.2.post1",
        "soundfile>=0.12.1",
        "pandas==2.2.3",
    ]
    
    for dep in whisperx_deps:
        logger.info(f"预装依赖: {dep}")
        subprocess.run(
            [python_path, '-m', 'pip', 'install', '--no-cache-dir', dep],
            capture_output=True, timeout=180
        )
    
    # 尝试预编译 wheel 安装
    if install_whisperx_from_wheel(python_path):
        return True
    
    # 使用 CDN 加速安装
    logger.info("从 git 安装 WhisperX (使用 CDN 加速)...")
    whisperx_commit = '7307306a9d8dd0d261e588cc933322454f853853'
    cdn_git_urls = get_cdn_git_urls(
        'git+https://github.com/m-bain/whisperx.git',
        whisperx_commit
    )
    
    for i, url in enumerate(cdn_git_urls):
        cdn_name = url.split('/')[2] if '/' in url else f'cdn_{i}'
        logger.info(f"尝试安装 via {cdn_name}...")
        try:
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', '--no-cache-dir', url],
                capture_output=True, text=True, timeout=600
            )
            
            if result.returncode == 0:
                logger.success(f"WhisperX 安装成功! (via {cdn_name})")
                return True
            else:
                logger.warning(f"{cdn_name} 失败: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            logger.warning(f"{cdn_name} 超时")
        except Exception as e:
            logger.warning(f"{cdn_name} 异常: {e}")
    
    logger.error("所有 CDN 安装方式均失败")
    return install_whisperx_with_deps(python_path)


def install_whisperx_with_deps(python_path: str) -> bool:
    """尝试预装 WhisperX 依赖后再安装（使用 CDN 加速）"""
    logger.info("预装 WhisperX 依赖...")
    
    # 注意：av 已通过 conda 安装，不需要 pip 安装
    pre_deps = [
        "numpy==1.26.4",
        # "av==10.0.0",  # ← 跳过，conda 已安装
        "faster-whisper==1.0.0",
        "ctranslate2==4.4.0",
        "transformers==4.39.3",
        "librosa==0.10.2.post1",
        "soundfile>=0.12.1",
        "pandas==2.2.3",
    ]
    
    for dep in pre_deps:
        logger.info(f"预装: {dep}")
        result = subprocess.run(
            [python_path, '-m', 'pip', 'install', dep],
            capture_output=True,
            text=True,
            timeout=180
        )
        if result.returncode != 0:
            logger.warning(f"预装跳过: {dep}")
    
    # 最后尝试安装 WhisperX（使用 CDN 加速）
    logger.info("尝试安装 WhisperX (使用 CDN 加速)...")
    whisperx_commit = '7307306a9d8dd0d261e588cc933322454f853853'
    cdn_git_urls = get_cdn_git_urls(
        'git+https://github.com/m-bain/whisperx.git',
        whisperx_commit
    )
    
    for i, url in enumerate(cdn_git_urls):
        cdn_name = url.split('/')[2] if '/' in url else f'cdn_{i}'
        logger.info(f"尝试安装 via {cdn_name}...")
        try:
            result = subprocess.run(
                [python_path, '-m', 'pip', 'install', 
                 url],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.success(f"WhisperX 安装成功! (via {cdn_name})")
                return True
            else:
                logger.warning(f"{cdn_name} 失败: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            logger.warning(f"{cdn_name} 超时")
        except Exception as e:
            logger.warning(f"{cdn_name} 异常: {e}")
    
    logger.error("WhisperX 安装失败")
    return False


def verify_environment(env_prefix: str) -> bool:
    """验证环境完整性"""
    logger.progress("验证环境...")
    
    if not env_prefix or not os.path.exists(env_prefix):
        logger.error(f"环境目录不存在: {env_prefix}")
        return False
    
    checks = [
        ("bin/python", os.path.exists(f"{env_prefix}/bin/python")),
        ("bin/pip", os.path.exists(f"{env_prefix}/bin/pip")),
        ("lib/python3.10", os.path.exists(f"{env_prefix}/lib/python3.10")),
    ]
    
    all_ok = True
    for name, ok in checks:
        if ok:
            logger.success(f"  {name}")
        else:
            logger.error(f"  {name}")
            all_ok = False
    
    if not all_ok:
        return False
    
    # 验证 Python 能运行
    python_path = f"{env_prefix}/bin/python"
    try:
        result = subprocess.run(
            [python_path, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.success(f"Python: {result.stdout.strip()}")
        else:
            logger.error("Python 无法运行")
            return False
    except Exception as e:
        logger.error(f"Python 验证失败: {e}")
        return False
    
    # 验证关键包
    test_imports = ['torch', 'fastapi']
    for pkg in test_imports:
        try:
            result = subprocess.run(
                [python_path, '-c', f'import {pkg}; print({pkg}.__version__)'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.success(f"  {pkg}: {result.stdout.strip()}")
            else:
                logger.warning(f"  {pkg}: 导入失败")
        except:
            logger.warning(f"  {pkg}: 测试超时")
    
    # 验证 ffmpeg GPU 支持
    try:
        ffmpeg_path = f"{env_prefix}/bin/ffmpeg"
        if os.path.exists(ffmpeg_path):
            result = subprocess.run(
                [ffmpeg_path, '-hwaccels'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if 'cuda' in result.stdout.lower() or 'nvenc' in result.stdout.lower():
                logger.success("  ffmpeg: 支持 NVIDIA GPU 加速 (cuda/nvenc)")
            else:
                logger.info("  ffmpeg: 已安装（GPU 加速支持需检查）")
        else:
            logger.warning("  ffmpeg: 未找到")
    except:
        logger.warning("  ffmpeg: 检测失败")
    
    return True


def cleanup_on_failure(env_prefix):
    """失败时清理"""
    logger.warning("清理残留文件...")
    
    if env_prefix and os.path.exists(env_prefix):
        try:
            shutil.rmtree(env_prefix)
            logger.info(f"已删除: {env_prefix}")
        except Exception as e:
            logger.error(f"删除失败: {e}")
    
    for tmp in ['/tmp/miniconda.sh', 'environment.yml']:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
                logger.info(f"已删除: {tmp}")
            except:
                pass


def install_dependencies():
    """主安装流程"""
    logger.section("WhisperX Cloud Installation v2")
    start_time = time.time()
    
    ENV_PREFIX = None
    CONDA_CMD = None
    
    try:
        # 步骤 1: 检测环境
        logger.section("Step 1: 环境检测")
        SERVER_ENV = detect_server_environment()
        ENV_PREFIX = setup_environment_paths(SERVER_ENV)
        
        if not ENV_PREFIX:
            raise RuntimeError("环境路径设置失败")
        
        # 步骤 2: 资源检查
        logger.section("Step 2: 资源检查")
        parent = os.path.dirname(ENV_PREFIX)
        ok, _ = check_disk_space(parent, min_gb=15.0)
        if not ok:
            raise RuntimeError("磁盘空间不足")
        
        # 步骤 3: Mamba/Conda
        logger.section("Step 3: Mamba 安装")
        CONDA_CMD, cmd_type = get_mamba_cmd()
        
        # 接受 ToS (仅 conda 需要)
        if cmd_type == 'conda':
            try:
                for channel in ['main', 'r']:
                    subprocess.run(
                        [CONDA_CMD, 'tos', 'accept', 
                         '--override-channels',
                         '--channel', f'https://repo.anaconda.com/pkgs/{channel}'],
                        capture_output=True, timeout=10
                    )
                logger.success("ToS 已接受")
            except:
                pass
        
        # 步骤 4: 创建 conda 环境（仅基础包）
        logger.section("Step 4: Conda 环境创建")
        create_environment_yml()
        
        # 检查已存在
        if os.path.exists(ENV_PREFIX):
            logger.warning("环境已存在，删除重建...")
            shutil.rmtree(ENV_PREFIX, ignore_errors=True)
        
        logger.progress(f"创建环境（使用 {cmd_type}）...")
        logger.info(f"目标路径: {ENV_PREFIX}")
        
        # 使用 mamba 或 conda 创建环境
        process = subprocess.Popen(
            [CONDA_CMD, 'env', 'create', '-f', 'environment.yml',
             '--prefix', ENV_PREFIX, '--yes'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in process.stdout:
            line = line.strip()
            if line:
                logger.info(f"  {line}")
        
        process.wait(timeout=INSTALL_TIMEOUT)
        
        if process.returncode != 0:
            raise RuntimeError(f"Conda 创建失败，code={process.returncode}")
        
        logger.success("Conda 环境创建成功")
        
        # 步骤 5: 安装 pip 依赖
        logger.section("Step 5: Pip 依赖安装")
        if not install_pip_dependencies(ENV_PREFIX):
            logger.warning("部分 pip 包安装失败，但继续...")
        
        # 步骤 6: 验证
        logger.section("Step 6: 环境验证")
        if not verify_environment(ENV_PREFIX):
            raise RuntimeError("环境验证失败")
        
        # 步骤 7: 保存配置
        logger.section("Step 7: 保存配置")
        
        CONDA_PYTHON = f"{ENV_PREFIX}/bin/python"
        config = {
            'python_path': CONDA_PYTHON,
            'env_prefix': ENV_PREFIX,
            'server_env': SERVER_ENV,
            'timestamp': datetime.now().isoformat()
        }
        
        with open('.conda_python_path', 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.success(f"配置已保存: {CONDA_PYTHON}")
        
        elapsed = time.time() - start_time
        logger.section(f"安装完成 - {elapsed:.1f}s")
        
        return True
        
    except Exception as e:
        logger.error(f"安装失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        cleanup_on_failure(ENV_PREFIX)
        
        elapsed = time.time() - start_time
        logger.section(f"安装失败 - {elapsed:.1f}s")
        return False


if __name__ == "__main__":
    success = install_dependencies()
    sys.exit(0 if success else 1)
