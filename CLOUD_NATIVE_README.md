# VideoLingo 云原生部署指南

## 概述

VideoLingo 云原生模式让您可以在**没有GPU的设备**上运行完整的视频翻译流程,所有AI计算(语音识别、人声分离)通过远程云服务完成。

### 优势对比

| 特性 | 传统本地模式 | 云原生模式 |
|------|-------------|-----------|
| GPU要求 | NVIDIA GPU 8GB+ | 无需GPU |
| 内存占用 | 8GB+ | 2-4GB |
| 存储占用 | 5GB+ (模型文件) | <500MB |
| 安装时间 | 30-60分钟 | 5分钟 |
| 适用设备 | 高性能工作站 | 笔记本/服务器/云主机 |
| 离线使用 | ✅ 支持 | ❌ 需要网络 |

## 快速开始

### 1. 部署远程云服务 (需要GPU服务器)

在具有GPU的机器上部署 unified_server:

```bash
# 进入 whisperx_cloud 目录
cd whisperx_cloud

# 安装依赖 (在GPU服务器上)
pip install -r requirements.txt

# 启动服务
python unified_server.py
```

或使用 Jupyter Notebook (推荐用于 Colab/Kaggle):
- 打开 `whisperx_cloud/Unified_Cloud_Server.ipynb`
- 运行所有单元格

### 2. 配置 VideoLingo (本地机器)

编辑 `config.yaml`:

```yaml
cloud_native:
  enabled: true
  cloud_url: 'https://your-server-url.ngrok-free.app'  # 替换为您的服务地址
  connection:
    timeout: 300
    max_retries: 3
    retry_delay: 5
  features:
    asr: true           # 使用云端ASR
    separation: true    # 使用云端人声分离

# 保持原有配置
demucs: true
whisper:
  runtime: 'local'  # 在云原生模式下保持local,会自动使用云端
  language: 'zh'    # 根据您的视频语言设置
```

### 3. 安装轻量级依赖

```bash
# 安装云原生依赖 (无需PyTorch!)
pip install -r requirements_cloud.txt
```

### 4. 验证环境

```bash
python check_cloud_native.py
```

### 5. 启动 VideoLingo

```bash
streamlit run st.py
```

## 架构说明

### 本地计算 (轻量级)
- **FFmpeg**: 视频/音频格式转换
- **pydub**: 音频分割/合并
- **spacy**: NLP文本处理
- **OpenCV**: 图像处理
- **streamlit**: Web界面

### 远程计算 (GPU服务)
- **WhisperX Cloud**: 语音识别 (ASR)
- **Demucs Cloud**: 人声/背景分离

所有远程服务通过 `whisperx_cloud/unified_client.py` 统一调用。

## 故障排除

### 连接失败

```
❌ Cannot connect to cloud service
```

解决方案:
1. 确认云服务是否运行: `curl https://your-server-url.ngrok-free.app/`
2. 检查防火墙设置
3. 确认URL配置正确

### 缺少依赖

```
❌ Missing module: requests
```

解决方案:
```bash
pip install -r requirements_cloud.txt
```

### 内存不足

云原生模式内存占用较低,如仍遇到问题:
- 减少并发处理数
- 增加swap空间

## 从本地模式迁移

### 1. 备份现有配置

```bash
cp config.yaml config.yaml.backup
```

### 2. 卸载重型依赖 (可选)

```bash
pip uninstall torch torchaudio whisperx demucs
```

### 3. 启用云原生模式

编辑 `config.yaml`, 添加 `cloud_native` 配置段。

### 4. 验证

```bash
python check_cloud_native.py
```

## 高级配置

### 使用 ngrok 暴露本地服务

```bash
# 安装 ngrok
pip install pyngrok

# 设置token
export NGROK_AUTHTOKEN=your_token_here

# 启动服务 (会自动创建隧道)
python whisperx_cloud/unified_server.py
```

### 自定义超时设置

```yaml
cloud_native:
  connection:
    timeout: 600      # 长视频需要更长的超时
    max_retries: 5    # 增加重试次数
    retry_delay: 10   # 增加重试间隔
```

## 安全建议

1. **使用HTTPS**: 确保 cloud_url 使用 https://
2. **访问控制**: 在生产环境中添加API密钥验证
3. **数据隐私**: 云服务器会处理音频数据,请遵守相关法规

## 技术支持

- 查看详细设计文档: `CLOUD_NATIVE_DESIGN.md`
- 云服务文档: `whisperx_cloud/README.md`
- 环境检测: `python check_cloud_native.py`
