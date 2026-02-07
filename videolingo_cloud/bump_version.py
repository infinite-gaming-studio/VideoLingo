#!/usr/bin/env python3
"""
版本号自动管理脚本

用法:
    python bump_version.py patch   # 2.4.0 -> 2.4.1
    python bump_version.py minor   # 2.4.0 -> 2.5.0
    python bump_version.py major   # 2.4.0 -> 3.0.0
    python bump_version.py show    # 显示当前版本
"""

import re
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).parent / "_version.py"


def get_current_version():
    """从 _version.py 读取当前版本"""
    content = VERSION_FILE.read_text(encoding='utf-8')
    match = re.search(r'__version__ = "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        raise ValueError("无法解析版本号")
    return tuple(int(x) for x in match.groups())


def bump_version(version_type='patch'):
    """增加版本号"""
    major, minor, patch = get_current_version()
    
    if version_type == 'patch':
        patch += 1
    elif version_type == 'minor':
        minor += 1
        patch = 0
    elif version_type == 'major':
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"未知的版本类型: {version_type}")
    
    new_version = f"{major}.{minor}.{patch}"
    
    # 更新 _version.py
    content = VERSION_FILE.read_text(encoding='utf-8')
    content = re.sub(
        r'__version__ = "\d+\.\d+\.\d+"',
        f'__version__ = "{new_version}"',
        content
    )
    VERSION_FILE.write_text(content, encoding='utf-8')
    
    return new_version


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'show':
        version = '.'.join(str(x) for x in get_current_version())
        print(f"当前版本: {version}")
    elif command in ('patch', 'minor', 'major'):
        old_version = '.'.join(str(x) for x in get_current_version())
        new_version = bump_version(command)
        print(f"✅ 版本已更新: {old_version} -> {new_version}")
        print(f"   文件: {VERSION_FILE}")
        print(f"\n提示: 请提交更改到 Git")
        print(f"   git add videolingo_cloud/_version.py")
        print(f'   git commit -m "chore(version): bump to {new_version}"')
    else:
        print(f"错误: 未知命令 '{command}'")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
