# WhisperX Cloud API Server ☁️

Standalone WhisperX ASR service for VideoLingo. Deploy on cloud GPU platforms (Google Colab, Kaggle, etc.) or local GPU servers.

## 🎯 Features

- ✅ Word-level timestamp alignment
- ✅ Multi-language support
- ✅ Optional speaker diarization
- ✅ FastAPI-based REST API
- ✅ ngrok tunnel for public URLs
- ✅ Compatible with VideoLingo cloud runtime

## 📋 Requirements

- Python 3.9 - 3.11 (3.10 recommended)
- NVIDIA GPU with CUDA 11.8+ (for GPU acceleration)
- 4GB+ GPU memory (8GB+ recommended for large-v3 model)

## 🚀 Installation

### Option 1: Conda (Recommended for Local GPU Servers)

Conda provides better environment isolation and automatic CUDA dependency management.

```bash
# Method 1: Using environment.yml
conda env create -f environment.yml
conda activate whisperx-cloud

# Method 2: Using installation script
python install_conda.py
```

### Option 2: Pip (For Colab/Kaggle)

```bash
# Install PyTorch with CUDA 11.8
pip install torch==2.0.0+cu118 torchaudio==2.0.0+cu118 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# Install other dependencies
pip install -r requirements.txt
```

### Option 3: Jupyter Notebook (Colab/Kaggle)

Open `WhisperX_Cloud_Unified.ipynb` in Google Colab or Kaggle and run all cells.

## 🔧 Configuration

Create a `.env` file or set environment variables:

```bash
# Required for public URL (get from https://dashboard.ngrok.com)
NGROK_AUTH_TOKEN=your_token_here

# Server configuration
PORT=8000
HOST=0.0.0.0

# HuggingFace settings (for China users)
HF_ENDPOINT=https://hf-mirror.com
```

## ▶️ Usage

### Start Server

```bash
# Activate conda environment (if using conda)
conda activate whisperx-cloud

# Start server
python whisperx_server.py
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/transcribe` | POST | Transcribe audio file |
| `/cache` | DELETE | Clear model cache |
| `/stats` | GET | Server statistics |

### Example Request

```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "audio=@audio.wav" \
  -F "model=large-v3" \
  -F "language=zh"
```

## 🔗 VideoLingo Integration

### Method 1: config.yaml

```yaml
whisper:
  runtime: 'cloud'
  whisperX_cloud_url: 'https://xxxx.ngrok-free.app'  # Your server URL
```

### Method 2: Environment Variable

```bash
export WHISPERX_CLOUD_URL='https://xxxx.ngrok-free.app'
```

### Method 3: Python Client

```python
from whisperx_cloud_client import WhisperXCloudClient

client = WhisperXCloudClient(base_url='https://xxxx.ngrok-free.app')
result = client.transcribe('audio.wav', language='zh')
```

## 📁 File Structure

```
whisperx_cloud/
├── environment.yml           # Conda environment configuration
├── install_conda.py          # Conda installation script
├── requirements.txt          # Pip dependencies with detailed comments
├── whisperx_server.py        # FastAPI server implementation
├── whisperx_cloud_client.py  # Python client for VideoLingo
├── WhisperX_Cloud_Unified.ipynb  # Universal notebook for Colab/Kaggle
└── README.md                 # This file
```

## 🔬 Dependency Versions

Dependencies are pinned to match VideoLingo parent project for compatibility:

| Package | Version | Notes |
|---------|---------|-------|
| torch | 2.0.0 | Synced with VideoLingo |
| whisperx | commit 7307306 | Pinned for stability |
| ctranslate2 | 4.4.0 | Required by whisperX |
| transformers | 4.39.3 | HuggingFace models |
| fastapi | 0.109.0 | API framework |

## 🐛 Troubleshooting

### GPU Not Detected

```bash
# Check CUDA installation
nvidia-smi

# Verify PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

### Model Download Slow

```bash
# For China users, use mirror
export HF_ENDPOINT=https://hf-mirror.com
```

### Out of Memory

- Use smaller model: `medium` or `small`
- Reduce batch_size in requests
- Disable speaker diarization

## 📚 References

- [VideoLingo Parent Project](../README.md)
- [WhisperX Documentation](https://github.com/m-bain/whisperX)
- [VideoLingo Configuration](../config.yaml)

## 📄 License

Same as VideoLingo parent project.
