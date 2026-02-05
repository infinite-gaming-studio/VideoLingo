# 文件重命名说明

## 变更记录

### 2025-02-05

**重命名文件:**
- 旧名称: `core/asr_backend/whisperX_local.py`
- 新名称: `core/asr_backend/whisperX_asr.py`

**原因:**
原文件名 `whisperX_local.py` 容易引起歧义,因为该模块实际上支持两种模式:
1. **本地模式**: 使用本地 GPU 运行 WhisperX
2. **云原生模式**: 调用远程 WhisperX 云服务

新名称 `whisperX_asr.py` 更准确,表明这是一个通用的 ASR (自动语音识别) 模块,支持多种后端。

**已更新的引用:**
1. `core/_2_asr.py` - 2处导入语句
2. `whisperx_cloud/whisperx_cloud_client.py` - 1处注释

**向后兼容性:**
该变更是内部实现细节,不影响用户配置或 API 使用。用户只需确保:
1. 使用新的文件路径导入
2. 不需要修改 config.yaml 或其他配置文件
