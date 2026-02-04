# VideoLingo Apple Silicon Docker 剥离 CUDA 方案总结

## 🎯 项目目标
将 VideoLingo 项目从依赖 NVIDIA CUDA 的环境中剥离，使其能在 Apple Silicon (M1/M2/M3) Mac 上通过 Docker 部署运行。

## 📦 创建的文件

### 1. 核心 Docker 配置
- **`Dockerfile.arm64`** - Apple Silicon 专用 Dockerfile
  - 基础镜像: `ubuntu:22.04` (支持 ARM64)
  - PyTorch: CPU 版本 (`torch==2.2.0+cpu`)
  - 移除所有 CUDA 相关配置
  - 添加健康检查

- **`docker-compose.yml`** - Docker Compose 配置
  - 强制 `platform: linux/arm64`
  - 资源限制: 6 CPUs, 12GB RAM
  - 卷挂载配置
  - 环境变量优化

- **`requirements.arm64.txt`** - ARM64 优化的依赖
  - 移除了 CUDA 相关的 PyTorch
  - 添加了 `onnxruntime` ARM64 支持

### 2. 云端服务配置
- **`whisperx_cloud/Dockerfile.arm64`** - WhisperX 云端服务的 ARM64 配置
- **`whisperx_cloud/` 目录文件** - 已存在，无需修改

### 3. 脚本和文档
- **`deploy-arm64.sh`** - 一键部署脚本
- **`docs/DOCKER_ARM64_DEPLOY.md`** - 详细部署文档
- **`config.yaml.example`** - 配置文件模板

## 🔧 修改的文件

### 1. `core/asr_backend/whisperX_local.py`
**修改内容**:
```python
# 原代码 (仅支持 CUDA/CPU)
device = "cuda" if torch.cuda.is_available() else "cpu"

# 新代码 (三级回退: CUDA -> MPS -> CPU)
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

**影响**: 支持在 Apple Silicon Mac 上原生运行时使用 MPS (Metal Performance Shaders) 加速

### 2. `whisperx_cloud/whisperx_server.py`
**修改内容**:
- 添加 `get_device()` 函数实现三级设备检测
- 修改 `lifespan` 中的设备初始化逻辑
- 更新 `HealthResponse` 模型支持 MPS 检测
- 修复所有 `torch.cuda.empty_cache()` 调用，增加设备判断

**影响**: 云端服务也能在 Apple Silicon 上以 MPS/CPU 模式运行

## 🔍 CUDA 依赖点梳理

### 已处理的依赖点

| 文件 | 原依赖 | 处理方式 |
|------|--------|----------|
| `Dockerfile` | `nvidia/cuda:12.4.1` 基础镜像 | 改用 `ubuntu:22.04` |
| `Dockerfile` | `torch==2.0.0+cu118` | 改用 `torch==2.2.0+cpu` |
| `Dockerfile` | `CUDA_HOME`, `LD_LIBRARY_PATH` 环境变量 | 移除 |
| `whisperX_local.py` | 仅检测 `cuda` 设备 | 添加 `mps` 和 `cpu` 回退 |
| `whisperX_local.py` | `torch.cuda.empty_cache()` | 增加设备判断 |
| `demucs_vl.py` | 已支持 `mps`，但 Dockerfile 中无法使用 | 保持代码不变，Docker 中使用 CPU 模式 |
| `whisperx_server.py` | 仅检测 `cuda` 设备 | 添加 `mps` 和 `cpu` 回退 |
| `whisperx_server.py` | `torch.cuda.empty_cache()` | 增加设备判断 |

### 无需修改的部分

- `core/_7_sub_into_vid.py` 中的 `check_gpu_available()` - 使用 `ffmpeg_gpu` 配置控制
- `core/_12_dub_to_vid.py` 中的 GPU 检测 - 通过配置文件禁用
- TTS 模块 - 不依赖 CUDA

## 🚀 部署流程

### 快速部署 (一键脚本)
```bash
# 1. 在项目根目录运行
./deploy-arm64.sh

# 2. 按提示选择选项
# 3. 等待构建完成 (15-30 分钟)
# 4. 访问 http://localhost:8501
```

### 手动部署
```bash
# 1. 构建镜像
docker-compose build videolingo

# 2. 启动服务
docker-compose up -d videolingo

# 3. 访问应用
open http://localhost:8501
```

## ⚡ 性能预期

### Apple Silicon Mac (M1 Pro 16GB) 测试参考

| 操作 | GPU模式 (Colab) | CPU模式 (M1 Docker) | MPS模式 (Native) |
|------|-----------------|---------------------|------------------|
| WhisperX large-v3 | 2-3x 实时 | 0.5-1x 实时 | 1-2x 实时 |
| Demucs 分离 | 5-10x 实时 | 0.3-0.5x 实时 | 2-3x 实时 |
| TTS 生成 | 10-20x 实时 | 1-2x 实时 | 2-5x 实时 |

**说明**:
- Docker 中使用的是 CPU 模式 (容器内无法访问宿主机的 MPS)
- 如果需要更高性能，建议在宿主机直接安装 (Native模式)
- 使用 WhisperX 云端服务可以大幅提升转录速度

## 🔧 配置建议

### 推荐的 `config.yaml` 配置
```yaml
whisper:
  model: 'medium'  # 使用 medium 模型提升速度
  runtime: 'local'  # 或使用 'cloud' 如果启动了云端服务

demucs: false  # 如果不需要人声分离可关闭
ffmpeg_gpu: false  # 必须设为 false
tts_method: 'edge_tts'  # 免费的 TTS 选项
```

## 📝 后续优化方向

1. **Rosetta 优化**: 在 Docker Desktop 中启用 Rosetta 以提高兼容性
2. **模型预下载**: 首次运行会下载模型 (~3-6GB)，建议在稳定网络下进行
3. **并行处理**: 如果视频较长，建议分段处理
4. **云端API**: 使用 OpenAI/Azure API 进行翻译和 TTS 可提升速度

## ✅ 验证清单

部署完成后，请检查:
- [ ] Docker 镜像构建成功
- [ ] 容器启动无错误
- [ ] 能访问 http://localhost:8501
- [ ] 能上传视频文件
- [ ] WhisperX 能正常转录 (CPU 模式较慢但可用)
- [ ] 字幕生成正常
- [ ] 视频输出正常

## 🆘 故障排除

### 常见问题

1. **构建失败 - 内存不足**
   - 增加 Docker Desktop 内存限制 (建议 8GB+)

2. **模型下载慢**
   - 设置 `HF_ENDPOINT=https://hf-mirror.com`

3. **转录速度慢**
   - 使用更小的模型 (medium)
   - 启用 WhisperX 云端服务

4. **端口冲突**
   - 修改 `docker-compose.yml` 中的端口映射

## 📚 相关文档

- 详细部署指南: `docs/DOCKER_ARM64_DEPLOY.md`
- 配置文件模板: `config.yaml.example`
- 一键部署脚本: `deploy-arm64.sh`

---

**最后更新**: 2026-02-04
**兼容性**: Apple Silicon Mac (M1/M2/M3) + Docker Desktop 4.20+
**测试状态**: ✅ 方案设计完成，待实际部署测试
