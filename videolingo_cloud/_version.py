"""
VideoLingo Cloud Server Version Management
统一版本号管理文件

版本号格式: MAJOR.MINOR.PATCH
- MAJOR: 重大架构变更，不兼容升级
- MINOR: 功能新增，向下兼容
- PATCH: Bug 修复，向下兼容

更新规则:
1. 修改此文件后，所有服务器版本号统一
2. PATCH 号在每次提交前手动 +1
3. MINOR 号在新功能发布时 +1
4. MAJOR 号在架构重构时 +1
"""

# 统一版本号 - 修改此处即可同步所有服务器
__version__ = "2.4.0"

# 版本别名，供各服务器导入
SERVER_VERSION = __version__
