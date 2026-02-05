# Docker安装

VideoLingo 提供了Dockerfile,可自行使用Dockerfile打包目前VideoLingo。以下是打包和运行的详细说明:

## 系统要求

### NVIDIA GPU 环境
- CUDA版本 > 12.4
- NVIDIA Driver版本> 550

### Apple Silicon (M1/M2/M3) Mac
- macOS 12.0+ (Monterey 或更高版本)
- Docker Desktop 4.20+ (启用 Rosetta)
- 至少 16GB RAM (推荐 32GB)

---

## Apple Silicon (ARM64) Docker 部署

对于 Apple Silicon Mac 用户，我们提供了专门的 ARM64 配置，完全剥离 CUDA 依赖，使用 CPU/MPS 模式运行。

### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/infinite-gaming-studio/VideoLingo.git
cd VideoLingo

# 2. 运行一键部署脚本
./deploy-arm64.sh
```

### 手动部署

```bash
# 构建镜像
docker-compose build videolingo

# 启动服务
docker-compose up -d videolingo

# 访问应用
open http://localhost:8501
```

### 配置说明

创建 `config.yaml` 配置文件:

```yaml
display_language: "zh-CN"

api:
  key: 'your-api-key-here'
  base_url: 'https://api.openai.com/v1'
  model: 'gpt-4'

target_language: '简体中文'

whisper:
  model: 'large-v3'  # 建议使用 'medium' 提升速度
  language: 'zh'
  runtime: 'local'

demucs: true
burn_subtitles: true
ffmpeg_gpu: false  # 必须设为 false
tts_method: 'edge_tts'
```

### 性能优化建议

1. **使用较小的模型**: 将 `whisper.model` 设为 `'medium'` 可提升 2-3 倍速度
2. **关闭人声分离**: 如不需要，设置 `demucs: false`
3. **使用云端 WhisperX**: 启动 WhisperX 云端服务提升转录速度

---

## NVIDIA GPU Docker 部署

## 构建和运行Docker镜像或者从DokerHub拉取

```bash
# 构建Docker镜像
docker build -t videolingo .

# 运行Docker容器
docker run -d -p 8501:8501 --gpus all videolingo
```

### 从DockerHub拉取

您可以直接从DockerHub拉取预构建的VideoLingo镜像:

```bash
docker pull rqlove/videolingo:latest
```

拉取完成后,使用以下命令运行容器:

```bash
docker run -d -p 8501:8501 --gpus all rqlove/videolingo:latest
```

注意: 
- `-d` 参数使容器在后台运行
- `-p 8501:8501` 将容器的8501端口映射到主机的8501端口
- `--gpus all` 启用所有可用的GPU支持
- 确保使用完整的镜像名称 `rqlove/videolingo:latest`

## 模型

whisper 模型不包含在镜像中,会在容器首次运行时自动下载。如果您希望跳过自动下载过程,可以从以下链接下载模型权重:

- [Google Drive链接](https://drive.google.com/file/d/10gPu6qqv92WbmIMo1iJCqQxhbd1ctyVw/view?usp=drive_link)
- [百度网盘链接](https://pan.baidu.com/s/1hZjqSGVn3z_WSg41-6hCqA?pwd=2kgs)

下载后,使用以下命令运行容器,将模型文件挂载到容器中:

```bash
docker run -d -p 8501:8501 --gpus all -v /path/to/your/model:/app/_model_cache rqlove/videolingo:latest
```

请注意将 `/path/to/your/model` 替换为您实际下载模型文件的本地路径。

## 其他说明

### NVIDIA GPU 镜像
- 基础镜像: nvidia/cuda:12.4.1-devel-ubuntu20.04
- Python版本: 3.10
- 预装软件: git, curl, sudo, ffmpeg, fonts-noto等
- PyTorch版本: 2.0.0 (CUDA 11.8)
- 暴露端口: 8501 (Streamlit应用)

### Apple Silicon 镜像
- 基础镜像: ubuntu:22.04 (ARM64)
- Python版本: 3.10
- PyTorch版本: 2.2.0 (CPU版本)
- 支持 MPS/CPU 设备检测
- 包含 WhisperX 云端服务配置

### 相关文档

- [详细部署指南 (中文)](../../ARM64_MIGRATION_SUMMARY.md)
- [Apple Silicon Docker 部署详解](../../docs/DOCKER_ARM64_DEPLOY.md)

