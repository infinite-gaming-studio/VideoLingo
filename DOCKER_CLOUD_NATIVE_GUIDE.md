# VideoLingo Docker 云原生部署指南 (macOS Apple Silicon)

## 概述

本指南介绍如何在 **macOS Apple Silicon (M1/M2/M3)** 上使用 Docker 部署 VideoLingo 云原生版本。

### 什么是云原生模式？

云原生模式将 GPU 密集型计算（语音识别、人声分离）卸载到远程云服务，本地仅保留轻量级处理：

| 组件 | 本地容器 | 远程云服务 |
|------|---------|-----------|
| 视频处理 | ✅ FFmpeg | ❌ |
| 音频处理 | ✅ pydub | ❌ |
| NLP处理 | ✅ spacy | ❌ |
| ASR识别 | ❌ | ✅ WhisperX Cloud |
| 人声分离 | ❌ | ✅ Demucs Cloud |

### 系统要求

- **macOS**: 12.0 (Monterey) 或更高版本
- **芯片**: Apple Silicon (M1/M2/M3)
- **内存**: 建议 8GB 或更多
- **存储**: 至少 5GB 可用空间
- **Docker**: Docker Desktop 4.0+
- **网络**: 需要连接远程云服务

## 快速开始

### 1. 安装 Docker Desktop

1. 下载 [Docker Desktop for Mac (Apple Silicon)](https://docs.docker.com/desktop/install/mac-install/)
2. 双击 `.dmg` 文件并拖拽到 Applications
3. 启动 Docker Desktop
4. 等待 Docker 引擎启动完成

### 2. 克隆项目

```bash
git clone https://github.com/infinite-gaming-studio/VideoLingo.git
cd VideoLingo
```

### 3. 配置云原生模式

编辑 `config.yaml` 文件：

```yaml
cloud_native:
  enabled: true
  cloud_url: 'https://your-cloud-server.ngrok-free.app'  # 替换为你的云服务地址
  connection:
    timeout: 300
    max_retries: 3
    retry_delay: 5
  features:
    asr: true
    separation: true

# 其他配置保持默认
demucs: true
whisper:
  runtime: 'local'  # 在云原生模式下保持 local，会自动使用云端
  language: 'zh'    # 根据你的视频语言设置
```

### 4. 启动服务

使用提供的启动脚本：

```bash
# 赋予执行权限
chmod +x start-cloud-native.sh

# 启动服务
./start-cloud-native.sh
```

首次启动会构建 Docker 镜像（约 5-10 分钟），后续启动仅需几秒钟。

### 5. 访问 VideoLingo

启动完成后，在浏览器中访问：

```
http://localhost:8501
```

## 手动操作（高级）

如果你不想使用启动脚本，可以手动执行 Docker 命令：

### 构建镜像

```bash
docker-compose -f docker-compose.cloud-native.yml build
```

### 启动服务

```bash
docker-compose -f docker-compose.cloud-native.yml up -d
```

### 查看日志

```bash
docker-compose -f docker-compose.cloud-native.yml logs -f
```

### 停止服务

```bash
docker-compose -f docker-compose.cloud-native.yml down
```

### 完全删除（包括数据卷）

```bash
docker-compose -f docker-compose.cloud-native.yml down -v
```

## 目录结构

```
VideoLingo/
├── input/                    # 放置输入视频
├── output/                   # 输出结果
├── _model_cache/             # 轻量级模型缓存
├── temp/                     # 临时文件
├── logs/                     # 日志文件
├── config.yaml               # 配置文件
├── docker-compose.cloud-native.yml
├── Dockerfile.cloud-native
└── start-cloud-native.sh
```

## 使用流程

### 1. 准备视频

将视频文件放入 `input/` 目录：

```bash
cp your-video.mp4 input/
```

### 2. 启动处理

1. 打开浏览器访问 `http://localhost:8501`
2. 在 Web 界面中配置参数
3. 点击开始处理

### 3. 获取结果

处理完成后，结果会保存在 `output/` 目录中。

## 常见问题

### Q1: 构建镜像很慢或失败

**解决方案：**
- 确保网络连接良好
- 使用国内镜像源（编辑 Dockerfile 取消注释相关行）
- 增加 Docker 内存限制（Docker Desktop → Settings → Resources）

### Q2: 无法连接到云服务

**错误信息：**
```
Cannot connect to cloud service
```

**解决方案：**
1. 检查云服务是否运行：
   ```bash
   curl https://your-cloud-server.ngrok-free.app/
   ```
2. 确认 `config.yaml` 中的 `cloud_url` 配置正确
3. 检查网络防火墙设置

### Q3: 容器启动后立即退出

**查看日志：**
```bash
docker-compose -f docker-compose.cloud-native.yml logs
```

**常见原因：**
- 配置文件错误
- 端口被占用
- 内存不足

### Q4: 处理视频时内存不足

**解决方案：**
1. 增加 Docker 内存限制：
   - Docker Desktop → Settings → Resources → Memory
   - 建议设置为 8GB 或更高

2. 或者修改 `docker-compose.cloud-native.yml`：
   ```yaml
   deploy:
     resources:
       limits:
         memory: 16G  # 增加内存限制
   ```

### Q5: 如何更新代码

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
./start-cloud-native.sh --rebuild
```

## 性能优化

### 1. 启用 Docker 的 Rosetta 支持

在 Docker Desktop 设置中：
- Settings → Features in development
- 启用 "Use Rosetta for x86/amd64 emulation"

### 2. 分配更多资源

根据你的 Mac 配置调整：
- CPU: 建议分配 4-6 核
- 内存: 建议分配 8-12GB
- Swap: 建议启用 2-4GB

### 3. 使用卷缓存

已配置在 `docker-compose.cloud-native.yml` 中：
```yaml
volumes:
  - ./input:/app/input:cached
  - ./output:/app/output:cached
```

## 安全建议

1. **不要提交敏感信息**：确保 `config.yaml` 中的 API 密钥已正确配置
2. **使用 HTTPS**：生产环境请使用 HTTPS 连接云服务
3. **定期更新**：保持 Docker 和基础镜像更新
4. **数据备份**：定期备份 `output/` 和 `config.yaml`

## 故障排除

### 检查容器状态

```bash
# 查看运行中的容器
docker ps

# 查看容器日志
docker logs videolingo-cloud

# 进入容器内部
docker exec -it videolingo-cloud /bin/bash
```

### 重置环境

如果遇到无法解决的问题，可以重置环境：

```bash
# 停止并删除容器
docker-compose -f docker-compose.cloud-native.yml down -v

# 删除镜像
docker rmi videolingo:cloud-native-arm64

# 重新构建并启动
./start-cloud-native.sh --rebuild
```

## 升级指南

### 升级到新版本

```bash
# 1. 保存当前配置
cp config.yaml config.yaml.backup

# 2. 拉取最新代码
git pull origin main

# 3. 恢复配置（或手动合并）
cp config.yaml.backup config.yaml

# 4. 重新构建并启动
./start-cloud-native.sh --rebuild
```

## 对比：云原生 vs 本地模式

| 特性 | 云原生 (Docker) | 本地 GPU 模式 |
|------|----------------|---------------|
| **GPU要求** | 不需要 | 需要 NVIDIA GPU |
| **安装时间** | 5分钟 | 30-60分钟 |
| **镜像大小** | ~2GB | ~8GB+ |
| **网络依赖** | 需要 | 可选 |
| **处理速度** | 依赖网络 | 依赖本地 GPU |
| **适用场景** | 开发测试、笔记本 | 生产环境、工作站 |

## 获取帮助

- **GitHub Issues**: [提交问题](https://github.com/infinite-gaming-studio/VideoLingo/issues)
- **云原生文档**: [CLOUD_NATIVE_README.md](./CLOUD_NATIVE_README.md)
- **设计文档**: [CLOUD_NATIVE_DESIGN.md](./CLOUD_NATIVE_DESIGN.md)

## 许可证

与 VideoLingo 主项目保持一致。
