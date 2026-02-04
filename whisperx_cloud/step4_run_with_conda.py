#!/usr/bin/env python3
"""
Step 4: 使用 Conda 环境运行脚本
读取 .conda_python_path 并使用该 Python 执行指定脚本
"""

import subprocess
import sys
import os
import json


def run_with_conda(script_path):
    """使用 conda 环境的 Python 运行脚本"""
    conda_python = None
    
    # 读取 conda Python 路径
    try:
        with open('.conda_python_path', 'r') as f:
            content = f.read().strip()
            # 尝试解析 JSON
            try:
                config = json.loads(content)
                conda_python = config.get('python_path')
            except json.JSONDecodeError:
                # 旧格式：纯文本路径
                conda_python = content
    except:
        pass
    
    # 如果读取失败，尝试默认路径
    if not conda_python:
        # 检测环境
        IN_COLAB = (
            'google.colab' in sys.modules or
            os.path.exists('/content') or
            'COLAB_GPU' in os.environ
        )
        IN_KAGGLE = os.path.exists('/kaggle')
        
        if IN_COLAB:
            if os.path.exists('/content/drive/MyDrive'):
                conda_python = '/content/drive/MyDrive/conda-envs/whisperx-cloud/bin/python'
            else:
                conda_python = '/content/conda-envs/whisperx-cloud/bin/python'
        elif IN_KAGGLE:
            conda_python = '/kaggle/working/conda-envs/whisperx-cloud/bin/python'
        else:
            conda_python = os.path.expanduser('~/miniconda3/envs/whisperx-cloud/bin/python')
    
    # 验证路径存在
    if not os.path.exists(conda_python):
        print(f"❌ Conda Python not found at: {conda_python}")
        print("Please run Step 3 first to install dependencies.")
        sys.exit(1)
    
    # 使用 conda 环境运行脚本
    print(f"🐍 Using Conda Python: {conda_python}")
    print(f"🚀 Running: {script_path}")
    result = subprocess.run([conda_python, script_path])
    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step4_run_with_conda.py <script_to_run.py>")
        sys.exit(1)
    
    script = sys.argv[1]
    sys.exit(run_with_conda(script))
