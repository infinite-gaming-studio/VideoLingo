#!/usr/bin/env python3
"""
Step 4: 使用 Conda 环境运行脚本
读取 .conda_python_path 并使用该 Python 执行指定脚本
"""

import subprocess
import sys
import os


def run_with_conda(script_path):
    """使用 conda 环境的 Python 运行脚本"""
    # 读取 conda Python 路径
    try:
        with open('.conda_python_path', 'r') as f:
            conda_python = f.read().strip()
    except:
        # 尝试默认路径
        conda_python = os.path.expanduser('~/miniconda3/envs/whisperx-cloud/bin/python')
        if not os.path.exists(conda_python):
            conda_python = '/kaggle/working/conda-envs/whisperx-cloud/bin/python'
        if not os.path.exists(conda_python):
            print("❌ Conda Python not found. Please run Step 4 first.")
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
