#!/usr/bin/env python3
"""
WhisperX Cloud 简化安装脚本 (Mamba 一键安装版)

直接在 Notebook 中运行，无需复杂的分步脚本
"""

import subprocess
import sys
import os
import json
from pathlib import Path

def run_cmd(cmd, timeout=300, check=True):
    """运行命令并返回结果"""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and check:
        print(f"Error: {result.stderr}")
        return False
    return result.returncode == 0

def install():
    """一键安装 WhisperX 环境"""
    
    # 检测环境
    in_colab = 'google.colab' in sys.modules or os.path.exists('/content')
    in_kaggle = os.path.exists('/kaggle')
    
    if in_colab:
        base_path = '/content/conda-envs/whisperx-cloud'
    elif in_kaggle:
        base_path = '/kaggle/working/conda-envs/whisperx-cloud'
    else:
        base_path = os.path.expanduser('~/conda-envs/whisperx-cloud')
    
    print(f"🚀 WhisperX Cloud 简化安装")
    print(f"环境路径: {base_path}")
    
    # 1. 安装 Mamba (如果还没有)
    mamba_bin = os.path.expanduser('~/miniforge3/bin/mamba')
    if not os.path.exists(mamba_bin):
        print("\n📦 安装 Miniforge (包含 Mamba)...")
        run_cmd(['wget', '-q', '-O', '/tmp/miniforge.sh',
                 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh'])
        run_cmd(['bash', '/tmp/miniforge.sh', '-b', '-p', os.path.expanduser('~/miniforge3')])
    else:
        print("✅ Mamba 已安装")
    
    # 2. 创建环境 (使用 mamba 直接安装所有包)
    print("\n📦 创建 Conda 环境并安装 WhisperX...")
    
    # 删除旧环境
    if os.path.exists(base_path):
        print("清理旧环境...")
        run_cmd([mamba_bin, 'remove', '-p', base_path, '--all', '-y'], check=False)
    
    # 创建环境并安装所有包 (关键：conda-forge 有预编译的 whisperx!)
    packages = [
        'python=3.10',
        'pytorch=2.0.0',
        'torchaudio=2.0.0',
        'pytorch-cuda=11.8',
        'ffmpeg',
        'whisperx',  # <-- 关键：conda-forge 预编译版，无需自己构建!
        'fastapi',
        'uvicorn',
        'python-multipart',
        'pyngrok',
        'requests',
        'nest_asyncio',
    ]
    
    cmd = [mamba_bin, 'create', '-p', base_path, '-c', 'conda-forge', '-c', 'pytorch', '-c', 'nvidia', '-y'] + packages
    
    print("这可能需要 5-10 分钟...")
    if not run_cmd(cmd, timeout=1800):
        print("❌ 环境创建失败")
        return False
    
    # 3. 保存配置
    config = {
        'python_path': f'{base_path}/bin/python',
        'env_prefix': base_path,
    }
    with open('.conda_python_path', 'w') as f:
        json.dump(config, f, indent=2)
    
    # 4. 验证
    print("\n✅ 验证安装...")
    python = f'{base_path}/bin/python'
    
    for pkg in ['torch', 'whisperx', 'fastapi']:
        result = subprocess.run([python, '-c', f'import {pkg}; print("OK")'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ {pkg}")
        else:
            print(f"  ⚠️ {pkg}: {result.stderr[:100]}")
    
    print(f"\n🎉 安装完成!")
    print(f"Python 路径: {python}")
    return True

if __name__ == '__main__':
    success = install()
    sys.exit(0 if success else 1)
