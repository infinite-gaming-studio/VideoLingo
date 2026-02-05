# VideoLingo 云原生改造方案

## 1. 架构目标

### 1.1 目标
- 剥离所有本地GPU计算依赖(WhisperX、Demucs、PyTorch)
- 保留轻量级本地计算(FFmpeg、pydub、spacy、OpenCV)
- 统一调用whisperx_cloud远程服务进行ASR和音频分离
- 通过配置灵活切换本地/云端模式

### 1.2 技术架构

```
VideoLingo (轻量级)
├── 本地计算层 (CPU only)
│   ├── FFmpeg - 音视频处理
│   ├── pydub - 音频分割/合并
│   ├── spacy - NLP文本处理
│   └── OpenCV - 图像处理
│
└── 云服务层 (Remote GPU)
    ├── WhisperX Cloud - ASR识别
    └── Demucs Cloud - 人声分离
        (通过 unified_client.py 统一调用)
```

## 2. 文件改造清单

### 2.1 核心文件修改

| 文件路径 | 改造内容 | 优先级 |
|---------|---------|--------|
| `config.yaml` | 添加cloud_native配置段 | High |
| `core/_2_asr.py` | 支持纯云模式流程 | High |
| `core/asr_backend/whisperX_local.py` | 移除torch/whisperx依赖,调用远程 | High |
| `core/asr_backend/demucs_vl.py` | 简化本地逻辑,优先使用云客户端 | High |
| `requirements.txt` | 创建requirements_cloud.txt轻量版 | Medium |
| `core/utils/` | 添加云服务健康检查工具 | Medium |

### 2.2 依赖变更

**移除的依赖(仅本地GPU模式需要):**
```
# AI/ML (Heavy)
torch==2.0.0
torchaudio==2.0.0
whisperx @ git+...
demucs[dev] @ git+...
ctranslate2==4.4.0
transformers==4.39.3
pytorch-lightning==2.3.3
lightning==2.3.3
```

**保留的轻量级依赖:**
```
# 核心功能
requests>=2.32.3
pydub==0.25.1
pandas==2.2.3
numpy==1.26.4
pyyaml==6.0.2

# 视频处理
moviepy==1.0.3
opencv-python==4.10.0.84

# NLP
spacy==3.7.4

# API
openai==1.55.3

# 工具
rich
streamlit==1.38.0
```

## 3. 配置方案

### 3.1 config.yaml 新增配置

```yaml
cloud_native:
  enabled: true
  cloud_url: 'https://your-cloud-server.ngrok-free.app'
  connection:
    timeout: 300
    max_retries: 3
    retry_delay: 5
  features:
    asr: true
    separation: true
```

## 4. 实施步骤

### Phase 1: 配置与检测
1. 修改config.yaml添加cloud_native配置段
2. 创建云服务健康检查工具

### Phase 2: 核心改造
1. 改造whisperX_local.py支持远程调用
2. 优化demucs_vl.py云原生逻辑
3. 更新_2_asr.py流程适配

### Phase 3: 依赖优化
1. 创建requirements_cloud.txt轻量依赖
2. 添加环境检测脚本

## 5. 优势对比

| 特性 | 本地模式 | 云原生模式 |
|-----|---------|-----------|
| GPU要求 | 需要NVIDIA GPU | 仅需CPU |
| 内存占用 | 8GB+ | 2GB |
| 存储占用 | 5GB+ | <500MB |
| 安装时间 | 30-60分钟 | 5分钟 |
