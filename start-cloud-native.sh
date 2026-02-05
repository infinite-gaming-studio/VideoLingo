#!/bin/bash

# VideoLingo Cloud Native 启动脚本
# 适用于 macOS Apple Silicon (M1/M2/M3) 和其他 ARM64 设备
# VideoLingo Cloud Native Startup Script
# For macOS Apple Silicon (M1/M2/M3) and other ARM64 devices

set -e

# 颜色定义 / Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的信息 / Print colored message
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装 / Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装 / Docker is not installed"
        echo "请安装 Docker Desktop for Mac: https://docs.docker.com/desktop/install/mac-install/"
        echo "Please install Docker Desktop for Mac: https://docs.docker.com/desktop/install/mac-install/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker 守护进程未运行 / Docker daemon is not running"
        echo "请启动 Docker Desktop"
        echo "Please start Docker Desktop"
        exit 1
    fi
    
    print_success "Docker 检查通过 / Docker check passed"
}

# 检查Docker Compose / Check Docker Compose
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose 未安装 / Docker Compose is not installed"
        exit 1
    fi
    print_success "Docker Compose 检查通过 / Docker Compose check passed"
}

# 检查云原生配置 / Check cloud-native configuration
check_cloud_config() {
    if [ ! -f "deploy_instance/config.yaml" ]; then
        if [ -f "config.yaml" ]; then
            print_info "正在初始化 deploy_instance/config.yaml... / Initializing deploy_instance/config.yaml..."
            cp config.yaml deploy_instance/config.yaml
        else
            print_error "未找到 config.yaml，无法初始化 deploy_instance/config.yaml / config.yaml not found, cannot initialize deploy_instance/config.yaml"
            exit 1
        fi
    fi
    
    CONFIG_FILE="deploy_instance/config.yaml"
    
    # 检查是否启用了云原生模式 / Check if cloud-native mode is enabled
    if grep -q "enabled: true" $CONFIG_FILE && grep -q "cloud_native:" $CONFIG_FILE; then
        print_success "云原生模式已启用 / Cloud-native mode is enabled"
        
        # 检查云URL配置 / Check cloud URL configuration
        if grep -q "cloud_url:" $CONFIG_FILE; then
            CLOUD_URL=$(grep "cloud_url:" $CONFIG_FILE | head -1 | sed 's/.*cloud_url: *//' | tr -d '"' | tr -d "'" | tr -d ' ')
            if [ -n "$CLOUD_URL" ] && [ "$CLOUD_URL" != "''" ] && [ "$CLOUD_URL" != '""' ]; then
                print_success "云服务URL配置: $CLOUD_URL"
                print_info "请确保云服务正在运行 / Please ensure cloud service is running"
            else
                print_warning "云服务URL未配置 / Cloud service URL not configured"
                print_info "请编辑 deploy_instance/config.yaml 设置 cloud_native.cloud_url"
                print_info "Please edit deploy_instance/config.yaml to set cloud_native.cloud_url"
            fi
        fi
    else
        print_warning "云原生模式未完全启用 / Cloud-native mode is not fully enabled"
        print_info "请编辑 config.yaml 设置 cloud_native.enabled: true"
        print_info "Please edit config.yaml to set cloud_native.enabled: true"
    fi
}

# 创建必要的目录 / Create necessary directories
create_directories() {
    print_info "创建部署目录 deploy_instance... / Creating deployment directory deploy_instance..."
    mkdir -p deploy_instance/input \
             deploy_instance/output \
             deploy_instance/_model_cache \
             deploy_instance/temp \
             deploy_instance/logs
    print_success "目录创建完成 / Directories created"
}

# 构建镜像 / Build image
build_image() {
    print_info "正在构建Docker镜像... / Building Docker image..."
    print_info "这可能需要5-10分钟，请耐心等待... / This may take 5-10 minutes, please be patient..."
    
    if docker-compose -f docker-compose.cloud-native.yml build; then
        print_success "镜像构建成功 / Image built successfully"
    else
        print_error "镜像构建失败 / Image build failed"
        exit 1
    fi
}

# 启动服务 / Start services
start_services() {
    print_info "正在启动 VideoLingo 云原生服务... / Starting VideoLingo cloud-native services..."
    
    # 停止旧容器（如果存在）/ Stop old containers if exist
    docker-compose -f docker-compose.cloud-native.yml down 2>/dev/null || true
    
    # 启动服务 / Start services
    if docker-compose -f docker-compose.cloud-native.yml up -d; then
        print_success "服务启动成功 / Services started successfully"
    else
        print_error "服务启动失败 / Failed to start services"
        exit 1
    fi
}

# 等待服务就绪 / Wait for service ready
wait_for_ready() {
    print_info "等待服务就绪... / Waiting for service to be ready..."
    
    local retries=30
    local wait_time=2
    
    for i in $(seq 1 $retries); do
        if curl -s -f http://localhost:8501/_stcore/health > /dev/null 2>&1; then
            print_success "VideoLingo 已就绪! / VideoLingo is ready!"
            return 0
        fi
        
        echo -n "."
        sleep $wait_time
    done
    
    print_error "服务启动超时 / Service startup timeout"
    print_info "请检查日志: docker-compose -f docker-compose.cloud-native.yml logs"
    return 1
}

# 显示访问信息 / Show access information
show_access_info() {
    echo ""
    echo "=========================================="
    print_success "VideoLingo 云原生模式已启动!"
    print_success "VideoLingo Cloud-Native Mode Started!"
    echo "=========================================="
    echo ""
    echo -e "🌐 访问地址 / Access URL: ${GREEN}http://localhost:8501${NC}"
    echo ""
    echo "📁 目录映射 / Directory mapping:"
    echo "   - 配置文件 / Config file:   ./deploy_instance/config.yaml"
    echo "   - 输入视频 / Input videos:  ./deploy_instance/input"
    echo "   - 输出结果 / Output results: ./deploy_instance/output"
    echo "   - 模型缓存 / Model cache:   ./deploy_instance/_model_cache"
    echo "   - 临时文件 / Temp files:    ./deploy_instance/temp"
    echo ""
    echo "📋 常用命令 / Common commands:"
    echo "   查看日志 / View logs:"
    echo "   docker-compose -f docker-compose.cloud-native.yml logs -f"
    echo ""
    echo "   停止服务 / Stop service:"
    echo "   docker-compose -f docker-compose.cloud-native.yml down"
    echo ""
    echo "   重启服务 / Restart service:"
    echo "   docker-compose -f docker-compose.cloud-native.yml restart"
    echo ""
    echo "=========================================="
}

# 主函数 / Main function
main() {
    echo "=========================================="
    echo " VideoLingo Cloud Native 启动脚本"
    echo " VideoLingo Cloud Native Startup Script"
    echo "=========================================="
    echo ""
    
    # 检查环境 / Check environment
    check_docker
    check_docker_compose
    check_cloud_config
    
    # 创建目录 / Create directories
    create_directories
    
    # 询问是否重新构建 / Ask if rebuild
    if [ "$1" = "--rebuild" ] || [ "$1" = "-r" ]; then
        print_info "重新构建模式 / Rebuild mode"
        build_image
    else
        # 检查镜像是否存在 / Check if image exists
        if ! docker images | grep -q "videolingo-cloud-mamba"; then
            print_info "首次运行，需要构建镜像... / First run, need to build image..."
            build_image
        else
            print_success "使用现有镜像 / Using existing image"
            print_info "如需重新构建，请使用: $0 --rebuild"
            print_info "To rebuild, use: $0 --rebuild"
        fi
    fi
    
    # 启动服务 / Start services
    start_services
    
    # 等待就绪 / Wait for ready
    if wait_for_ready; then
        show_access_info
        
        # 可选：自动打开浏览器 / Optional: auto open browser
        if command -v open &> /dev/null; then
            print_info "正在打开浏览器... / Opening browser..."
            sleep 2
            open http://localhost:8501
        fi
    fi
}

# 显示帮助 / Show help
show_help() {
    echo "VideoLingo Cloud Native 启动脚本"
    echo "VideoLingo Cloud Native Startup Script"
    echo ""
    echo "用法 / Usage: $0 [选项 / options]"
    echo ""
    echo "选项 / Options:"
    echo "  --rebuild, -r    重新构建Docker镜像 / Rebuild Docker image"
    echo "  --help, -h       显示帮助 / Show this help"
    echo ""
    echo "示例 / Examples:"
    echo "  $0               启动服务 / Start services"
    echo "  $0 --rebuild     重新构建并启动 / Rebuild and start"
    echo ""
}

# 处理参数 / Handle arguments
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --rebuild|-r)
        main "$1"
        ;;
    "")
        main
        ;;
    *)
        print_error "未知选项: $1 / Unknown option: $1"
        show_help
        exit 1
        ;;
esac
