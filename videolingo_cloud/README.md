# VideoLingo Cloud API Server ☁️

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

### Option 1: Mamba/Conda (Recommended for Local GPU Servers)

**Mamba** is recommended over Conda - it's 3-5x faster for dependency resolution and installation.

#### Prerequisites - Install Mamba (Recommended)

```bash
# Option A: Install Miniforge (includes Mamba) - RECOMMENDED
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p $HOME/miniforge3
export PATH="$HOME/miniforge3/bin:$PATH"

# Option B: Install Mamba in existing Conda
conda install -c conda-forge mamba -n base -y
```

#### Install WhisperX Cloud

```bash
# Method 1: Using environment.yml (auto-detects mamba/conda)
mamba env create -f environment.yml  # or: conda env create -f environment.yml
mamba activate whisperx-cloud        # or: conda activate whisperx-cloud

# Method 2: Using installation script (auto-detects mamba/conda)
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

### Option 3: Using Pre-compiled WhisperX Wheel (Fastest)

To avoid building WhisperX from source (which requires git and can be slow), you can use a pre-compiled wheel:

```bash
# Set environment variable to use custom wheel URL (optional)
export WHISPERX_WHEEL_URL="https://your-cdn.com/whisperx-3.1.1-py3-none-any.whl"

# Run installation - it will auto-detect and use pre-compiled wheel
python install_conda.py
```

Or manually install the wheel:

```bash
# Download pre-built wheel
pip install https://ghp.ci/https://github.com/user-attachments/files/whisperx-3.1.1-py3-none-any.whl

# Or build wheel locally
pip wheel git+https://github.com/m-bain/whisperx.git@7307306 --no-cache-dir -w ./wheels
pip install ./wheels/whisperx-*.whl
```

### Option 4: International CDN Acceleration (Auto-Enabled)

The installation script automatically uses multiple international CDNs to accelerate WhisperX git installation:

**Supported CDNs:**
- `ghps.cc` - GitHub proxy (global)
- `ghproxy.net` - GitHub proxy (USA)
- `github.moeyy.xyz` - Hong Kong node
- `gh.api.99988866.xyz` - USA node

**How it works:**
1. Tries pre-compiled wheel first (if URL provided)
2. Falls back to git installation with CDN acceleration
3. Automatically retries failed CDNs
4. Falls back to original GitHub as last resort

**Custom CDN:**
```bash
# Set custom git URL for WhisperX
export WHISPERX_GIT_URL="git+https://your-fast-mirror.com/m-bain/whisperx.git@7307306"
python install_conda.py
```

### Option 3: Jupyter Notebook (Colab/Kaggle)

Open `Unified_Cloud_Server.ipynb` in Google Colab or Kaggle and run all cells.

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
from videolingo_cloud.videolingo_cloud_client import VideoLingoCloudClient

client = VideoLingoCloudClient(base_url='https://xxxx.ngrok-free.app')
result = client.transcribe('audio.wav', language='zh')
```

## 📁 File Structure

```
videolingo_cloud/
├── environment.yml           # Conda/Mamba environment configuration
├── install_conda.py          # Mamba/Conda installation script
├── requirements.txt          # Pip dependencies with detailed comments
├── step3_install_deps.py     # Automated installation with mamba + wheel support
├── whisperx_server.py        # FastAPI server implementation (ASR)
├── demucs_server.py          # FastAPI server implementation (Separation)
├── unified_server.py         # Unified FastAPI server implementation
├── videolingo_cloud_client.py  # Python client for VideoLingo
├── Unified_Cloud_Server.ipynb  # Universal notebook for Colab/Kaggle
└── README.md                 # This file
```

## 🔬 Dependency Versions

Dependencies are pinned to match VideoLingo parent project for compatibility:

| Package | Version | Notes |
|---------|---------|-------|
| torch | 2.0.0 | Synced with VideoLingo |
| whisperx | commit 7307306 | Pinned for stability (CDN-accelerated git install) |
| ctranslate2 | 4.4.0 | Required by whisperX |
| transformers | 4.39.3 | HuggingFace models |
| fastapi | 0.109.0 | API framework |
| mamba | latest | 3-5x faster than conda |
| **CDN Support** | - | Auto-enabled: ghps.cc, ghproxy.net, etc. |

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

### CDN Installation Failures

The installation script automatically uses multiple international CDNs. If all fail:

```bash
# Use custom git mirror
export WHISPERX_GIT_URL="git+https://your-fast-mirror.com/m-bain/whisperx.git@7307306"
python install_conda.py
```

Or check network connectivity to CDNs:
```bash
curl -I https://ghps.cc
curl -I https://ghproxy.net
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
