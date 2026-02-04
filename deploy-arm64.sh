#!/bin/bash
# VideoLingo Apple Silicon Docker 快速启动脚本

set -e

echo "🚀 VideoLingo Apple Silicon Docker 部署脚本"
echo "============================================"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查是否在项目根目录
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ 错误: 请在 VideoLingo 项目根目录运行此脚本${NC}"
    exit 1
fi

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ 错误: Docker 未运行，请启动 Docker Desktop${NC}"
    exit 1
fi

# 检查 Docker Compose 版本
if docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo -e "${GREEN}✓ Docker 环境检查通过${NC}"

# 创建必要的目录
echo ""
echo "📁 创建必要的目录..."
mkdir -p input output models temp
echo -e "${GREEN}✓ 目录创建完成${NC}"

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  未找到 config.yaml，创建默认配置...${NC}"
    cat > config.yaml << 'EOF'
# VideoLingo 默认配置 (Apple Silicon 优化)
display_language: "zh-CN"

api:
  key: 'your-api-key-here'
  base_url: 'https://api.openai.com/v1'
  model: 'gpt-4'

target_language: '简体中文'

whisper:
  model: 'large-v3'
  language: 'zh'
  runtime: 'local'
  
demucs: true
burn_subtitles: true
ffmpeg_gpu: false
tts_method: 'edge_tts'
EOF
    echo -e "${GREEN}✓ 默认配置文件已创建${NC}"
    echo -e "${YELLOW}⚠️  请编辑 config.yaml 设置你的 API 密钥${NC}"
fi

# 询问是否构建镜像
echo ""
echo "🔨 是否需要构建 Docker 镜像?"
echo "   1) 首次部署或代码更新后 - 选择 1"
echo "   2) 仅启动现有镜像 - 选择 2"
read -p "请选择 (1/2): " BUILD_CHOICE

if [ "$BUILD_CHOICE" = "1" ]; then
    echo ""
    echo "🏗️  开始构建 Docker 镜像..."
    echo "   (这可能需要 15-30 分钟，请耐心等待...)"
    echo ""
    
    # 设置环境变量优化构建
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    $COMPOSE_CMD build --no-cache videolingo
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Docker 镜像构建成功${NC}"
    else
        echo -e "${RED}❌ Docker 镜像构建失败${NC}"
        exit 1
    fi
fi

# 询问是否启动 WhisperX 云端服务
echo ""
echo "☁️  是否启动 WhisperX 云端服务?"
echo "   1) 是 - 同时启动 (推荐用于提高转录速度)"
echo "   2) 否 - 仅启动主应用"
read -p "请选择 (1/2): " WHISPERX_CHOICE

# 启动服务
echo ""
echo "🚀 启动 VideoLingo 服务..."

if [ "$WHISPERX_CHOICE" = "1" ]; then
    $COMPOSE_CMD --profile whisperx up -d
    echo -e "${GREEN}✓ VideoLingo + WhisperX 云端服务已启动${NC}"
    echo ""
    echo "📍 访问地址:"
    echo "   - VideoLingo: http://localhost:8501"
    echo "   - WhisperX API: http://localhost:8000"
else
    $COMPOSE_CMD up -d videolingo
    echo -e "${GREEN}✓ VideoLingo 已启动${NC}"
    echo ""
    echo "📍 访问地址:"
    echo "   - VideoLingo: http://localhost:8501"
fi

# 等待服务启动
echo ""
echo "⏳ 等待服务启动 (约 30 秒)..."
sleep 10
echo "   服务启动中..."
sleep 10
echo "   服务启动中..."
sleep 10

# 检查服务健康状态
echo ""
echo "🏥 检查服务健康状态..."

if curl -s http://localhost:8501/_stcore/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ VideoLingo 服务运行正常${NC}"
else
    echo -e "${YELLOW}⚠️  VideoLingo 服务可能还在启动中${NC}"
fi

if [ "$WHISPERX_CHOICE" = "1" ]; then
    if curl -s http://localhost:8000/health > /dev/null 2>&1 || curl -s http://localhost:8000 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ WhisperX 云端服务运行正常${NC}"
    else
        echo -e "${YELLOW}⚠️  WhisperX 云端服务可能还在启动中${NC}"
    fi
fi

echo ""
echo "============================================"
echo -e "${GREEN}🎉 VideoLingo 部署完成!${NC}"
echo ""
echo "📖 常用命令:"
echo "   查看日志:   $COMPOSE_CMD logs -f videolingo"
echo "   停止服务:   $COMPOSE_CMD down"
echo "   重启服务:   $COMPOSE_CMD restart videolingo"
echo "   进入容器:   $COMPOSE_CMD exec videolingo bash"
echo ""
echo "📁 重要目录:"
echo "   输入视频:   ./input/"
echo "   输出结果:   ./output/"
echo "   模型缓存:   ./models/"
echo "   配置文件:   ./config.yaml"
echo ""
echo "🔧 如需修改配置，请编辑: config.yaml"
echo "   (修改后需要重启服务生效)"
echo ""
echo "🌐 请在浏览器中访问: http://localhost:8501"
echo "============================================"

# 显示运行中的容器
echo ""
echo "📊 运行中的容器:"
$COMPOSE_CMD ps
