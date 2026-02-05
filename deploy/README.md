# VideoLingo 部署指南

## 目录结构

```
deploy/
├── docker/
│   ├── Dockerfile.base      # 基础镜像（依赖，很少变更）
│   ├── Dockerfile.app       # 应用镜像（代码，频繁变更）
│   └── docker-compose.yml   # 部署配置
├── scripts/
│   └── build.sh             # 一键构建脚本
├── config/
│   └── config.yaml.example  # 配置模板
└── README.md                # 本文件
```

## 快速开始

### 1. 首次部署

```bash
cd deploy
./scripts/build.sh full
```

这会：
1. 构建基础镜像（包含所有依赖，约 5-10 分钟）
2. 构建应用镜像（复制代码，约 10 秒）
3. 启动服务

### 2. 代码更新后重新部署

```bash
./scripts/build.sh quick
```

这会：
1. 使用缓存的基础镜像
2. 只重新构建应用镜像（几秒钟）
3. 重启服务

### 3. 常用命令

```bash
# 启动服务
./scripts/build.sh start

# 停止服务
./scripts/build.sh stop

# 重启服务
./scripts/build.sh restart

# 查看日志
./scripts/build.sh logs
```

## 配置说明

### 云端服务配置

编辑 `deploy_instance/config.yaml`：

```yaml
cloud_native:
  enabled: true
  cloud_url: 'https://your-cloud-server.com'
  features:
    asr: true
    separation: true

whisper:
  whisperX_cloud_url: 'https://your-cloud-server.com'
  whisperX_token: 'your-token'
```

### API 配置

```yaml
api:
  key: 'YOUR_API_KEY'
  base_url: 'https://api.openai.com/v1'
  model: 'gpt-4'
```

## 数据持久化

以下目录通过 volume 挂载到容器：

| 本地路径 | 容器路径 | 说明 |
|---------|---------|------|
| `./deploy_instance/input` | `/app/input` | 输入视频 |
| `./deploy_instance/output` | `/app/output` | 输出结果 |
| `./deploy_instance/_model_cache` | `/app/_model_cache` | 模型缓存 |
| `./deploy_instance/temp` | `/app/temp` | 临时文件 |
| `./deploy_instance/config.yaml` | `/app/config.yaml` | 配置文件 |
| `./deploy_instance/logs` | `/app/logs` | 日志文件 |

## 访问服务

启动后访问：http://localhost:8501

## 故障排查

### 查看日志

```bash
docker-compose -f deploy/docker/docker-compose.yml logs -f
```

### 重新构建基础镜像

如果依赖有更新：

```bash
./scripts/build.sh full
```

### 清理重建

```bash
docker-compose -f deploy/docker/docker-compose.yml down -v
docker rmi videolingo:base videolingo:latest
./scripts/build.sh full
```
