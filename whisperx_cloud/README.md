# WhisperX Cloud Deployment

将 WhisperX 单独部署到 GPU 云服务器，VideoLingo 通过 API 调用。

## 📁 文件说明

```
whisperx_cloud/
├── whisperx_server.py           # FastAPI 服务端（独立部署时使用）
├── requirements.txt             # 精简依赖
├── WhisperX_Cloud_Unified.ipynb # ⭐ 统一部署 Notebook (支持 Colab/Kaggle/本地)
├── whisperx_cloud_client.py     # VideoLingo 客户端
└── README.md                    # 本文档
```

## 🚀 快速开始

### 1. 部署服务端

**推荐使用统一 Notebook (WhisperX_Cloud_Unified.ipynb):**

- ✅ **自动检测环境** - 支持 Colab/Kaggle/本地 GPU 服务器
- ✅ **一键部署** - 自动安装依赖、启动服务、创建隧道
- ✅ **内置 ngrok** - 自动生成公共 URL
- ✅ **智能配置** - 自动检测 GPU、调整 batch_size

**部署步骤:**

1. **Google Colab:**
   - 上传 `WhisperX_Cloud_Unified.ipynb` 到 Colab
   - Runtime → Change runtime type → GPU
   - 设置 ngrok token (下面有获取方法)
   - Runtime → Run all
   - 复制输出的 Public URL

2. **Kaggle:**
   - 上传 `WhisperX_Cloud_Unified.ipynb` 到 Kaggle
   - Settings → Accelerator → GPU T4 x2
   - 设置 ngrok token
   - Run all → 复制 URL

3. **本地 GPU 服务器:**
   ```bash
   # 方法 A: 使用 Notebook
   jupyter notebook WhisperX_Cloud_Unified.ipynb
   
   # 方法 B: 直接运行服务端
   pip install -r requirements.txt
   python whisperx_server.py
   # 配置反向代理或使用 ngrok
   ```

### 2. 配置 VideoLingo

编辑 `config.yaml`:

```yaml
whisper:
  runtime: 'cloud'
  whisperX_cloud_url: 'https://xxxx.ngrok-free.app'  # 从 Notebook 输出复制
  cloud_timeout: 300  # API 超时时间（秒）
```

或使用环境变量:
```bash
export WHISPERX_CLOUD_URL='https://xxxx.ngrok-free.app'
```

### 3. 测试连接

```python
# 在 VideoLingo 目录下运行
python whisperx_cloud/whisperx_cloud_client.py
```

## 🔧 进阶配置

### Notebook 配置选项

在 `WhisperX_Cloud_Unified.ipynb` 的第一个单元格中配置:

```python
# ngrok 认证令牌 (必需)
NGROK_AUTH_TOKEN = "你的_token"

# API 端口
SERVER_PORT = 8000

# 默认模型
DEFAULT_MODEL = "large-v3"  # 可选: tiny, base, small, medium, large-v1/v2/v3

# 是否启用说话人分离 (需要更多显存)
ENABLE_DIARIZATION = False

# HuggingFace 镜像 (中国大陆用户)
HF_ENDPOINT = "https://hf-mirror.com"
```

### API 端点

- `GET /` - 健康检查 + 服务器信息
- `GET /stats` - GPU 使用统计
- `POST /transcribe` - 转录音频
  - 参数: `audio` (文件), `language`, `model`, `align`, `speaker_diarization`
  - 返回: 带单词级时间戳的字幕
- `DELETE /cache` - 清除模型缓存（释放显存）

### 使用客户端类

```python
from whisperx_cloud.whisperx_cloud_client import WhisperXCloudClient, WhisperXConfig

# 创建配置
config = WhisperXConfig(
    cloud_url='https://xxxx.ngrok-free.app',
    default_model='large-v3',
    api_timeout=300
)

# 创建客户端
client = WhisperXCloudClient(config)

# 健康检查
info = client.health_check()

# 转录音频
result = client.transcribe(
    audio_path='audio.wav',
    language='zh',
    align=True
)

# 清理缓存
client.clear_cache()
```

## 🆓 免费 GPU 资源

| 平台 | GPU | 时长限制 | 特点 |
|------|-----|----------|------|
| Google Colab | T4 | 12小时/天 | 最稳定，易用 |
| Kaggle | T4 x2 | 30小时/周 | 双 GPU，适合大批量 |

## 📋 ngrok Token 获取

1. 访问 https://ngrok.com/signup 注册
2. 登录后访问 https://dashboard.ngrok.com/get-started/your-authtoken
3. 复制 token 粘贴到 Notebook 配置中

**注意:** ngrok 免费版 URL 每次重启会变。如需固定域名，请升级 ngrok Pro。

## 🔌 故障排除

### 1. "No cloud URL configured"

检查 `config.yaml`:
```yaml
whisper:
  runtime: 'cloud'
  whisperX_cloud_url: '你的URL'
```

### 2. ngrok 连接失败

- 检查 token 是否正确
- Kaggle 用户：确认 Settings → Internet 为 ON
- 尝试重新运行 Notebook 第 5、6 单元格

### 3. GPU 未检测到

- Colab: Runtime → Change runtime type → GPU
- Kaggle: Settings → Accelerator → GPU T4 x2

### 4. 模型下载慢

中国大陆用户在 Notebook 配置中设置:
```python
HF_ENDPOINT = "https://hf-mirror.com"
```

### 5. 显存不足

- 使用较小模型: `medium` 或 `small`
- 在 Notebook 配置中减小 `DEFAULT_MODEL`
- 禁用 `ENABLE_DIARIZATION`

## 🎯 优势

1. **节省本地资源** - 云端处理 ASR，本地只做后续步骤
2. **免费 GPU** - Colab/Kaggle 提供免费额度
3. **一键部署** - Notebook 自动完成所有配置
4. **跨平台** - 支持 Colab/Kaggle/本地 GPU 服务器
5. **兼容性好** - 返回格式与本地 whisperX 完全一致

## 🔄 工作流程

```
VideoLingo (本地) 
    ↓ 上传音频
WhisperX Cloud (Colab/Kaggle)
    ↓ 返回转录结果
VideoLingo (本地) 
    ↓ 继续翻译、配音等
```

## 📞 支持

有问题请查看:
1. Notebook 中的 "故障排除" 部分
2. 运行 `python whisperx_cloud/whisperx_cloud_client.py` 测试连接
3. 检查服务器健康: `curl https://your-url.ngrok-free.app/`

## 📝 License

与 VideoLingo 项目保持一致。
