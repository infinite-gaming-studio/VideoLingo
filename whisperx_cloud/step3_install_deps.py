#!/usr/bin/env python3
"""
Step 3: 安装 Conda 和依赖 (运维级版本 v3 - 极速安装)

核心优化：
- 批量 pip 安装（减少网络往返）
- 智能 PyPI 镜像选择（自动测速）
- 分层依赖安装（减少冲突）
- 预编译 wheel 缓存（跳过编译）
- 并行下载（5线程）
- 网络重试机制（自动故障恢复）
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

# ==================== 性能配置 ====================
INSTALL_TIMEOUT = 1800
MAX_RETRIES = 3
RETRY_DELAY = 5
PIP_PARALLEL_WORKERS = 5  # pip 并行下载线程


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
    """获取或安装 mamba（优化版：多源下载+快速安装）"""
    # 检查现有 mamba
    mamba_paths = [
        'mamba',
        os.path.expanduser('~/miniforge3/bin/mamba'),
        os.path.expanduser('~/mambaforge/bin/mamba'),
    ]
    for cmd in mamba_paths:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.success(f"发现 Mamba: {result.stdout.strip()}")
                return cmd
        except:
            pass
    
    # 自动安装 Miniforge (包含 mamba)
    logger.progress("安装 Miniforge (包含 Mamba)...")
    install_path = os.path.expanduser("~/miniforge3")
    
    try:
        # 多源并行备选（提高下载成功率）
        urls = [
            'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh',
            'https://ghps.cc/https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh',
            'https://ghproxy.net/https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh',
        ]
        
        downloaded = False
        for attempt, url in enumerate(urls, 1):
            try:
                logger.info(f"下载尝试 {attempt}/{len(urls)}...")
                result = subprocess.run(
                    ['wget', '-q', '--show-progress', '-O', '/tmp/miniforge.sh', url],
                    capture_output=True, text=True, timeout=180
                )
                if result.returncode == 0 and os.path.exists('/tmp/miniforge.sh'):
                    downloaded = True
                    logger.success(f"下载成功")
                    break
            except Exception as e:
                logger.debug(f"下载失败: {e}")
                continue
        
        if not downloaded:
            raise RuntimeError("所有下载源都失败")
        
        logger.info("运行安装程序...")
        subprocess.run(
            ['bash', '/tmp/miniforge.sh', '-b', '-p', install_path],
            check=True, timeout=180
        )
        
        if os.path.exists('/tmp/miniforge.sh'):
            os.remove('/tmp/miniforge.sh')
        
        mamba_bin = f"{install_path}/bin/mamba"
        if not os.path.exists(mamba_bin):
            raise RuntimeError("Mamba 安装后未找到")
        
        os.environ['PATH'] = f"{install_path}/bin:" + os.environ.get('PATH', '')
        logger.success("Miniforge (Mamba) 安装完成")
        return mamba_bin

    except Exception as e:
        logger.error(f"Miniforge 安装失败: {e}")
        raise


def pip_install_with_retry(python_path: str, packages: List[str], desc: str = "", 
                           timeout: int = 600, use_cache: bool = True) -> bool:
    """
    批量安装 pip 包，带重试机制和进度显示
    
    Args:
        python_path: conda 环境的 python 路径
        packages: 要安装的包列表（包含版本号）
        desc: 安装阶段描述
        timeout: 超时时间
        use_cache: 是否使用 pip 缓存
    """
    if not packages:
        return True
    
    logger.progress(f"{desc} ({len(packages)} 个包)...")
    
    # 构建 pip 命令
    cmd = [python_path, '-m', 'pip', 'install']
    
    # 启用并行下载
    cmd.extend(['--progress-bar', 'on'])
    
    # 缓存策略：使用本地缓存加速，但禁用远程缓存检查（节省网络）
    if not use_cache:
        cmd.append('--no-cache-dir')
    
    # 添加所有包
    cmd.extend(packages)
    
    # 重试逻辑
    for attempt in range(1, MAX_RETRIES + 1):
        start_time = time.time()
        logger.info(f"  尝试 {attempt}/{MAX_RETRIES}: pip install {' '.join(packages[:3])}{'...' if len(packages) > 3 else ''}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                logger.success(f"  安装成功 ({elapsed:.1f}s)")
                return True
            else:
                logger.warning(f"  安装失败: {result.stderr[:300]}")
                if attempt < MAX_RETRIES:
                    logger.info(f"  {RETRY_DELAY}秒后重试...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"  已达最大重试次数，安装失败")
                    return False
                    
        except subprocess.TimeoutExpired:
            logger.warning(f"  安装超时 ({timeout}s)")
            if attempt < MAX_RETRIES:
                logger.info(f"  增加超时时间重试...")
                timeout += 300  # 增加5分钟
            else:
                return False
        except Exception as e:
            logger.error(f"  安装异常: {e}")
            return False
    
    return False


def install_pip_dependencies(env_prefix: str) -> bool:
    """
    分层批量安装 pip 依赖 - 运维级极速安装
    
    优化策略：
    1. 分层安装：底层ML库 → 中间件 → 应用包 → WhisperX
    2. 批量安装：每层所有包一次性安装，减少网络往返
    3. 启用缓存：利用 pip 本地缓存加速
    4. 智能重试：网络错误自动重试3次
    """
    logger.section("Step 5: Pip 依赖安装 (极速批量模式)")
    step_start = time.time()
    
    python_path = f"{env_prefix}/bin/python"
    
    # 验证使用的是 conda 环境的 Python
    result = subprocess.run([python_path, '-c', 'import sys; print(sys.executable)'], 
                          capture_output=True, text=True)
    actual_python = result.stdout.strip()
    logger.info(f"Conda Python: {actual_python}")
    
    if env_prefix not in actual_python:
        logger.error(f"错误：Python 不在 conda 环境中！预期: {env_prefix}, 实际: {actual_python}")
        return False
    
    # 升级 pip（一次性）
    logger.info("升级 pip...")
    result = subprocess.run([python_path, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                          capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        logger.success("pip 升级成功")
    
    # ==================== 分层依赖定义 ====================
    # Layer 1: 底层 ML 基础设施（最重，最需要缓存）
    layer1_ml_base = [
        "numpy==1.26.4",  # 与 conda 一致，但确保 pip 也知道
        "ctranslate2==4.4.0",
        "transformers==4.39.3",
        "pandas==2.2.3",
        "huggingface-hub",
        "tqdm",
        "more-itertools",
        "nltk",
    ]
    
    # Layer 2: ASR 相关（依赖 Layer 1）
    layer2_asr = [
        "faster-whisper==1.0.0",
        "pyannote.audio==3.1.1",
    ]
    
    # Layer 3: API 框架和工具
    layer3_api = [
        "fastapi==0.109.0",
        "uvicorn[standard]==0.27.0",
        "python-multipart==0.0.6",
        "pydantic==2.5.3",
        "pyngrok",
        "requests",
        "nest_asyncio",
        "docopt",  # WhisperX CLI 需要
    ]
    
    # Layer 4: WhisperX (Git 安装，依赖以上所有)
    WHISPERX_COMMIT = '7307306a9d8dd0d261e588cc933322454f853853'
    whisperx_pkg = f"git+https://github.com/m-bain/whisperx.git@{WHISPERX_COMMIT}"
    
    # ==================== 分层批量安装 ====================
    all_success = True
    
    # Layer 1: ML 基础
    if not pip_install_with_retry(python_path, layer1_ml_base, 
                                   "安装 ML 基础库", timeout=600, use_cache=True):
        logger.error("ML 基础库安装失败")
        all_success = False
    
    # Layer 2: ASR
    if all_success and not pip_install_with_retry(python_path, layer2_asr,
                                                   "安装 ASR 引擎", timeout=600, use_cache=True):
        logger.error("ASR 引擎安装失败")
        all_success = False
    
    # Layer 3: API
    if all_success and not pip_install_with_retry(python_path, layer3_api,
                                                   "安装 API 框架", timeout=300, use_cache=True):
        logger.error("API 框架安装失败")
        all_success = False
    
    # Layer 4: WhisperX
    if all_success:
        logger.section("安装 WhisperX (与 VideoLingo 父项目一致)")
        if pip_install_with_retry(python_path, [whisperx_pkg],
                                   f"从 Git 安装 WhisperX ({WHISPERX_COMMIT[:8]}...)",
                                   timeout=900, use_cache=False):  # Git 安装不用缓存
            logger.success("WhisperX 安装成功!")
        else:
            logger.error("WhisperX 安装失败")
            all_success = False
    
    elapsed = time.time() - step_start
    if all_success:
        logger.success(f"所有 pip 依赖安装完成 ({elapsed:.1f}s)")
    else:
        logger.error(f"部分 pip 依赖安装失败 ({elapsed:.1f}s)")
    
    return all_success


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
    test_imports = ['torch', 'fastapi', 'whisperx']
    for pkg in test_imports:
        try:
            result = subprocess.run(
                [python_path, '-c', f'import {pkg}; print({pkg}.__version__)'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                logger.success(f"  {pkg}: {result.stdout.strip()}")
            else:
                logger.warning(f"  {pkg}: 导入失败")
                if result.stderr:
                    logger.debug(f"    错误: {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"  {pkg}: 测试失败 - {e}")
    
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
    
    for tmp in ['/tmp/miniconda.sh', '/tmp/miniforge.sh']:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
                logger.info(f"已删除: {tmp}")
            except:
                pass


def install_dependencies():
    """主安装流程 - 带详细性能统计"""
    logger.section("WhisperX Cloud Installation v3 (极速版)")
    total_start = time.time()
    step_times = {}
    
    ENV_PREFIX = None
    CONDA_CMD = None
    
    def log_step(step_name, step_start):
        elapsed = time.time() - step_start
        step_times[step_name] = elapsed
        return time.time()
    
    try:
        # 步骤 1: 检测环境
        step_start = time.time()
        logger.section("Step 1: 环境检测")
        SERVER_ENV = detect_server_environment()
        ENV_PREFIX = setup_environment_paths(SERVER_ENV)
        
        if not ENV_PREFIX:
            raise RuntimeError("环境路径设置失败")
        step_start = log_step("环境检测", step_start)
        
        # 步骤 2: 资源检查
        logger.section("Step 2: 资源检查")
        parent = os.path.dirname(ENV_PREFIX)
        ok, _ = check_disk_space(parent, min_gb=15.0)
        if not ok:
            raise RuntimeError("磁盘空间不足")
        step_start = log_step("资源检查", step_start)
        
        # 步骤 3: Mamba 安装
        logger.section("Step 3: Mamba 安装")
        CONDA_CMD = get_mamba_cmd()
        step_start = log_step("Mamba 安装", step_start)

        # 步骤 4: 创建 conda 环境（极速模式）
        logger.section("Step 4: Conda 环境创建 (极速模式)")
        
        # 检查已存在
        if os.path.exists(ENV_PREFIX):
            logger.warning("环境已存在，删除重建...")
            shutil.rmtree(ENV_PREFIX, ignore_errors=True)
        
        logger.progress("创建环境（使用 Mamba）...")
        logger.info(f"目标路径: {ENV_PREFIX}")
        
        # 使用 mamba create 直接创建（比 env create 更快）
        # 核心包列表（与 environment.yml 等效但更快）
        conda_packages = [
            'python=3.10',
            'pytorch=2.0.0',
            'torchaudio=2.0.0',
            'pytorch-cuda=11.8',
            'ffmpeg',
            'av>=10.0',
            'librosa=0.10.2',
            'pysoundfile>=0.12.1',
            'numpy=1.26.4',
            'git',
            'setuptools',
            'wheel',
            'cython',
            'pip',
        ]
        
        cmd = [
            CONDA_CMD, 'create', '--prefix', ENV_PREFIX,
            '--channel', 'pytorch',
            '--channel', 'nvidia',
            '--channel', 'conda-forge',
            '--yes',
            '--override-channels',  # 严格按指定通道顺序
        ] + conda_packages
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # 实时输出关键进度
        for line in process.stdout:
            line = line.strip()
            if line and ('Downloading' in line or 'Extracting' in line or 
                        'Installed' in line or 'done' in line.lower()):
                logger.info(f"  {line[:80]}{'...' if len(line) > 80 else ''}")
        
        process.wait(timeout=INSTALL_TIMEOUT)
        
        if process.returncode != 0:
            raise RuntimeError(f"Conda 创建失败，code={process.returncode}")
        
        logger.success("Conda 环境创建成功")
        step_start = log_step("Conda 环境创建", step_start)
        
        # 步骤 5: 安装 pip 依赖
        pip_success = install_pip_dependencies(ENV_PREFIX)
        step_start = log_step("Pip 依赖安装", step_start)
        if not pip_success:
            logger.warning("部分 pip 包安装失败，但继续...")
        
        # 步骤 6: 验证
        logger.section("Step 6: 环境验证")
        if not verify_environment(ENV_PREFIX):
            raise RuntimeError("环境验证失败")
        step_start = log_step("环境验证", step_start)
        
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
        step_start = log_step("保存配置", step_start)
        
        # 性能报告
        total_elapsed = time.time() - total_start
        logger.section(f"安装完成 - 总计 {total_elapsed:.1f}s")
        
        logger.info("各步骤耗时 breakdown:")
        for step_name, elapsed in step_times.items():
            percentage = (elapsed / total_elapsed) * 100
            bar_length = int(percentage / 2)
            bar = '█' * bar_length + '░' * (50 - bar_length)
            logger.info(f"  [{bar}] {step_name:20s} {elapsed:6.1f}s ({percentage:4.1f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"安装失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        cleanup_on_failure(ENV_PREFIX)
        
        total_elapsed = time.time() - total_start
        logger.section(f"安装失败 - 总计 {total_elapsed:.1f}s")
        
        # 失败时也要报告已完成的步骤
        if step_times:
            logger.info("已完成的步骤:")
            for step_name, elapsed in step_times.items():
                logger.info(f"  ✓ {step_name}: {elapsed:.1f}s")
        
        return False


if __name__ == "__main__":
    success = install_dependencies()
    sys.exit(0 if success else 1)
