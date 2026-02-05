# Docker Installation

VideoLingo provides a Dockerfile that you can use to build the current VideoLingo package. Here are detailed instructions for building and running:

## System Requirements

### NVIDIA GPU Environment
- CUDA version > 12.4
- NVIDIA Driver version > 550

### Apple Silicon (M1/M2/M3) Mac
- macOS 12.0+ (Monterey or later)
- Docker Desktop 4.20+ (with Rosetta enabled)
- At least 16GB RAM (32GB recommended)

---

## Apple Silicon (ARM64) Docker Deployment

For Apple Silicon Mac users, we provide dedicated ARM64 configurations that completely strip CUDA dependencies and run in CPU/MPS mode.

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/infinite-gaming-studio/VideoLingo.git
cd VideoLingo

# 2. Run one-click deployment script
./deploy-arm64.sh
```

### Manual Deployment

```bash
# Build image
docker-compose build videolingo

# Start services
docker-compose up -d videolingo

# Access application
open http://localhost:8501
```

### Configuration

Create `config.yaml` configuration file:

```yaml
display_language: "en-US"

api:
  key: 'your-api-key-here'
  base_url: 'https://api.openai.com/v1'
  model: 'gpt-4'

target_language: 'English'

whisper:
  model: 'large-v3'  # Use 'medium' for better speed
  language: 'en'
  runtime: 'local'

demucs: true
burn_subtitles: true
ffmpeg_gpu: false  # Must be set to false
tts_method: 'edge_tts'
```

### Performance Optimization Tips

1. **Use smaller model**: Set `whisper.model` to `'medium'` for 2-3x speed improvement
2. **Disable vocal separation**: Set `demucs: false` if not needed
3. **Use WhisperX Cloud**: Start WhisperX cloud service for faster transcription

---

## NVIDIA GPU Docker Deployment

## Building and Running the Docker Image or Pulling from DockerHub

```bash
# Build the Docker image
docker build -t videolingo .

# Run the Docker container
docker run -d -p 8501:8501 --gpus all videolingo
```

### Pulling from DockerHub

You can directly pull the pre-built VideoLingo image from DockerHub:

```bash
docker pull rqlove/videolingo:latest
```

After pulling, use the following command to run the container:

```bash
docker run -d -p 8501:8501 --gpus all rqlove/videolingo:latest
```

Note: 
- The `-d` parameter runs the container in the background
- `-p 8501:8501` maps port 8501 of the container to port 8501 of the host
- `--gpus all` enables support for all available GPUs
- Make sure to use the full image name `rqlove/videolingo:latest`

## Models

The Whisper model is not included in the image and will be automatically downloaded when the container is first run. If you want to skip the automatic download process, you can download the model weights from [here](https://drive.google.com/file/d/10gPu6qqv92WbmIMo1iJCqQxhbd1ctyVw/view?usp=drive_link) or [Baidu Netdisk](https://pan.baidu.com/s/1hZjqSGVn3z_WSg41-6hCqA?pwd=2kgs) (Passcode: 2kgs).

After downloading, use the following command to run the container, mounting the model file into the container:

```bash
docker run -d -p 8501:8501 --gpus all -v /path/to/your/model:/app/_model_cache rqlove/videolingo:latest
```

Please replace `/path/to/your/model` with the actual local path where you downloaded the model file.

## Additional Information

### NVIDIA GPU Image
- Base image: nvidia/cuda:12.4.1-devel-ubuntu20.04
- Python version: 3.10
- Pre-installed software: git, curl, sudo, ffmpeg, fonts-noto, etc.
- PyTorch version: 2.0.0 (CUDA 11.8)
- Exposed port: 8501 (Streamlit application)

### Apple Silicon Image
- Base image: ubuntu:22.04 (ARM64)
- Python version: 3.10
- PyTorch version: 2.2.0 (CPU version)
- Supports MPS/CPU device detection
- Includes WhisperX cloud service configuration

### Related Documentation

- [Detailed Deployment Guide](../../ARM64_MIGRATION_SUMMARY.md)
- [Apple Silicon Docker Deployment Guide](../../docs/DOCKER_ARM64_DEPLOY.md)

## Future Plans

- Continue to improve the Dockerfile to reduce image size
- Push the Docker image to Docker Hub
- Support mounting required models to the host machine using the -v parameter
