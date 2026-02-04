# VideoLingo Apple Silicon (ARM64) Docker 部署指南

## 📋 概述

本文档指导如何在 Apple Silicon Mac (M1/M2/M3) 上使用 Docker 部署 VideoLingo，**完全剥离 CUDA 依赖**，使用 CPU 模式运行。

## ✅ 已完成的工作

### 1. 创建的文件
- `Dockerfile.arm64` - Apple Silicon 专用的 Docker 配置
- `docker-compose.yml` - Docker Compose 配置文件
- `requirements.arm64.txt` - ARM64 优化的依赖列表
- `whisperx_cloud/Dockerfile.arm64` - WhisperX 云端服务的 ARM64 配置

### 2. 修改的文件
- `core/asr_backend/whisperX_local.py` - 支持 MPS/CPU 三级回退
- `whisperx_cloud/whisperx_server.py` - 支持 MPS/CPU 设备检测

## 🚀 快速开始

### 前提条件
- macOS 12.0+ (Monterey 或更高版本)
- Apple Silicon Mac (M1/M2/M3)
- Docker Desktop 4.20+ (启用 Rosetta for x86/amd64 emulation)
- 至少 16GB RAM (推荐 32GB)

### 步骤 1: 克隆仓库
```bash
git clone https://github.com/infinite-gaming-studio/VideoLingo.git
cd VideoLingo
```

### 步骤 2: 构建 Docker 镜像
```bash
# 构建 VideoLingo 主应用
docker-compose build videolingo

# 可选: 构建 WhisperX 云端服务
docker-compose --profile whisperx build whisperx-cloud
```

**构建时间**: 约 15-30 分钟 (取决于网络速度和Mac性能)

### 步骤 3: 启动服务
```bash
# 仅启动 VideoLingo
docker-compose up -d videolingo

# 或同时启动 VideoLingo + WhisperX 云端服务
docker-compose --profile whisperx up -d
```

### 步骤 4: 访问应用
打开浏览器访问: http://localhost:8501

## 📁 文件说明

### 1. Dockerfile.arm64
```dockerfile
# 关键特性:
- 基础镜像: ubuntu:22.04 (支持 ARM64)
- PyTorch: CPU 版本 (torch==2.2.0+cpu)
- 预装 spacy 模型
- 健康检查
- 资源限制优化
```

### 2. docker-compose.yml
```yaml
# 关键配置:
- platform: linux/arm64 (强制ARM64架构)
- 资源限制: 6 CPUs, 12GB RAM
- 卷挂载: input/, output/, models/, config.yaml
- 环境变量: CPU模式, 模型缓存路径
```

### 3. 代码修改

#### whisperX_local.py 设备检测逻辑:
```python
# 三级回退: CUDA -> MPS (Apple Silicon) -> CPU
if torch.cuda.is_available():
    device = "cuda"
    batch_size = 16
    compute_type = "float16"
elif torch.backends.mps.is_available():
    device = "mps"
    batch_size = 4
    compute_type = "float16"
else:
    device = "cpu"
    batch_size = 1
    compute_type = "int8"
```

## ⚙️ 配置说明

### 配置文件挂载
在 `docker-compose.yml` 中，以下文件会持久化到宿主机:
- `./config.yaml` - 主配置文件
- `./custom_terms.xlsx` - 自定义术语表
- `./input/` - 输入视频文件夹
- `./output/` - 输出结果文件夹
- `./models/` - 模型缓存文件夹

### 推荐的 config.yaml 配置
```yaml
# ASR 配置
whisper:
  model: 'large-v3'
  language: 'zh'  # 或 'en', 'auto' 等
  runtime: 'local'  # 使用本地模式
  
# 人声分离
demucs: true

# 字幕烧录
burn_subtitles: true
ffmpeg_gpu: false  # 禁用GPU加速

# TTS 选择
tts_method: 'edge_tts'  # 免费且质量好的选项
```

## 🐳 常用命令

```bash
# 查看日志
docker-compose logs -f videolingo

# 停止服务
docker-compose down

# 重启服务
docker-compose restart videolingo

# 进入容器shell
docker-compose exec videolingo bash

# 清理缓存
docker-compose exec videolingo rm -rf /app/temp/*

# 更新镜像 (代码修改后)
docker-compose build --no-cache videolingo
docker-compose up -d videolingo
```

## 🔧 故障排除

### 问题 1: 构建失败 - 内存不足
**解决方案**:
```bash
# 增加Docker内存限制 (Docker Desktop -> Settings -> Resources)
# 建议: 至少 8GB RAM, 4 CPUs

# 使用buildkit并限制并行度
DOCKER_BUILDKIT=1 docker-compose build videolingo
```

### 问题 2: 模型下载慢
**解决方案**:
```bash
# 设置 HuggingFace 镜像
export HF_ENDPOINT=https://hf-mirror.com

# 或在 docker-compose.yml 环境变量中添加:
# - HF_ENDPOINT=https://hf-mirror.com
```

### 问题 3: WhisperX 转录速度慢
**原因**: CPU模式比GPU慢很多

**解决方案**:
1. 使用更小的模型: `config.yaml` 中设置 `model: 'medium'`
2. 使用云端 WhisperX 服务
3. 缩短视频片段长度

### 问题 4: 端口冲突
**解决方案**:
```bash
# 修改 docker-compose.yml 中的端口映射
ports:
  - "8502:8501"  # 将宿主机的8502映射到容器的8501
```

### 问题 5: 权限错误
**解决方案**:
```bash
# 修复文件夹权限
chmod -R 777 ./input ./output ./models ./temp
```

## 📊 性能预期

在 Apple Silicon Mac 上运行性能参考:

| 操作 | CPU模式 | 备注 |
|------|---------|------|
| WhisperX (large-v3) | 0.5-1x 实时 | 10分钟视频需10-20分钟 |
| Demucs 人声分离 | 0.3-0.5x 实时 | 较慢 |
| TTS 生成 | 1-2x 实时 | 取决于TTS服务 |
| 字幕烧录 | 2-5x 实时 | 较快 |

**建议**:
- 使用 `medium` 模型代替 `large-v3` (速度提升2-3倍，精度略有下降)
- 关闭 `demucs` 如果不需人声分离
- 使用云端API (OpenAI/Azure) 进行TTS

## 🔗 架构对比

### 原架构 (CUDA)
```
VideoLingo (CUDA)
├── GPU: CUDA 12.4
├── PyTorch: cu118
├── WhisperX: GPU加速
└── Demucs: GPU加速
```

### 新架构 (ARM64/CPU)
```
VideoLingo (ARM64)
├── Platform: linux/arm64
├── PyTorch: CPU版本
├── WhisperX: CPU模式 (支持MPS回退)
└── Demucs: CPU模式 (支持MPS回退)
```

## 📝 后续优化建议

1. **启用 Rosetta**: 在 Docker Desktop 中启用 Rosetta 以提高 x86 二进制文件兼容性
2. **模型预下载**: 首次运行会下载模型，建议在稳定网络环境下进行
3. **使用 SSD**: 模型文件较大 (~3-6GB)，使用 SSD 可提高加载速度
4. **定期清理**: 运行 `docker system prune` 清理未使用的镜像和卷

## 🆘 获取帮助

- GitHub Issues: https://github.com/infinite-gaming-studio/VideoLingo/issues
- 查看日志: `docker-compose logs -f videolingo`
- 检查健康状态: `docker-compose ps`

---

**注意**: 此配置专为 Apple Silicon Mac 优化，不建议用于生产环境的高并发场景。如需更高性能，请考虑使用配备 NVIDIA GPU 的云服务器。
