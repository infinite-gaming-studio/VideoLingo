# VideoLingo 本地 Docker 部署指南

## 快速部署步骤

### 1. 确保 config.yaml 配置正确

```yaml
whisper:
  runtime: 'cloud'
  diarization: true
  min_speakers: 2
  max_speakers: 5

cloud_native:
  cloud_url: 'https://adiaphoristic-zaire-reminiscently.ngrok-free.dev'
  token: 'ac4dbb16-7d3f-4e6a-9a1a-b27672f1aac8'

speaker_voices:
  SPEAKER_00: 'zh-CN-XiaoxiaoNeural'
  SPEAKER_01: 'zh-CN-YunxiNeural'
  SPEAKER_02: 'zh-CN-YunjianNeural'
  SPEAKER_03: 'zh-CN-XiaoyiNeural'
```

### 2. 构建并运行 Docker

**第一次部署（需要构建基础镜像）：**
```bash
# 进入项目目录
cd /Users/nvozi/Coding/ai-based-projects/VideoLingo

# 构建基础镜像（只需执行一次）
docker-compose -f deploy/docker/docker-compose.yml build base

# 构建应用镜像（开发模式，使用本地代码）
BUILD_MODE=dev docker-compose -f deploy/docker/docker-compose.yml build app

# 启动服务
docker-compose -f deploy/docker/docker-compose.yml up -d
```

**后续更新（只需要重新构建应用）：**
```bash
# 更新代码后重新构建
git pull origin feature/speaker-diarization-tts
BUILD_MODE=dev docker-compose -f deploy/docker/docker-compose.yml build app

# 重启服务
docker-compose -f deploy/docker/docker-compose.yml up -d
```

### 3. 验证部署

```bash
# 查看容器状态
docker ps | grep videolingo

# 查看日志
docker logs -f videolingo-app

# 访问服务
open http://localhost:8501
```

### 4. 停止服务

```bash
docker-compose -f deploy/docker/docker-compose.yml down
```

## 常见问题

**Q: 容器无法启动**
```bash
# 检查日志
docker logs videolingo-app

# 检查端口占用
lsof -i :8501

# 重启服务
docker-compose -f deploy/docker/docker-compose.yml restart
```

**Q: 需要更新代码**
```bash
# 拉取最新代码
git pull origin feature/speaker-diarization-tts

# 重新构建并启动
BUILD_MODE=dev docker-compose -f deploy/docker/docker-compose.yml up -d --build
```

**Q: 清理所有数据**
```bash
docker-compose -f deploy/docker/docker-compose.yml down -v
docker volume prune
```

## 测试多角色功能

1. 访问 http://localhost:8501
2. 上传一个多角色视频（如 demo/demo-rzdf.mp3）
3. 在侧边栏确认 "Speaker Diarization" 已启用
4. 运行到 Step 2 (ASR) - 会自动识别说话人
5. 在 Speaker Voice Configuration 页面为每个角色选择声音
6. 继续运行到 TTS 步骤

## 文件映射说明

本地路径 → 容器路径：
- `./deploy_instance/input` → `/app/input` (输入文件)
- `./deploy_instance/output` → `/app/output` (输出文件)
- `./deploy_instance/_model_cache` → `/app/_model_cache` (模型缓存)
- `./config.yaml` → `/app/config.yaml` (配置文件)
