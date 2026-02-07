#!/bin/bash
# VideoLingo 快速构建脚本
# 支持多阶段构建，基础镜像依赖不常变更，应用镜像只包含代码

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 默认构建模式: prod (生产模式从GitHub克隆，dev模式使用本地代码)
BUILD_MODE="${BUILD_MODE:-dev}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查基础镜像是否存在
check_base_image() {
    if docker images | grep -q "^videolingo.*base"; then
        return 0
    else
        return 1
    fi
}

# 构建基础镜像
build_base() {
    log_info "构建基础镜像 (包含所有依赖，可能需要几分钟)..."
    docker-compose -f deploy/docker/docker-compose.yml build base
    log_success "基础镜像构建完成: videolingo:base"
}

# 构建应用镜像
build_app() {
    local mode=${1:-$BUILD_MODE}
    if [ "$mode" = "dev" ]; then
        log_info "构建应用镜像 [开发模式] - 使用本地代码..."
    else
        log_info "构建应用镜像 [生产模式] - 从 GitHub 克隆代码..."
    fi
    # 使用 --no-cache 强制重新构建，确保总是拉取最新代码
    BUILD_MODE=$mode docker-compose -f deploy/docker/docker-compose.yml build --no-cache app
    log_success "应用镜像构建完成: videolingo:latest (模式: $mode)"
}

# 启动服务
start() {
    log_info "启动 VideoLingo 服务..."
    docker-compose -f deploy/docker/docker-compose.yml up -d
    log_success "服务已启动，访问: http://localhost:8501"
}

# 停止服务
stop() {
    log_info "停止 VideoLingo 服务..."
    docker-compose -f deploy/docker/docker-compose.yml down
    log_success "服务已停止"
}

# 查看日志
logs() {
    docker-compose -f deploy/docker/docker-compose.yml logs -f
}

# 显示使用帮助
usage() {
    echo "VideoLingo 快速构建脚本"
    echo ""
    echo "用法: ./build.sh [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  full    完整构建（基础镜像 + 应用镜像），首次使用或依赖变更时执行"
    echo "  quick   快速构建（仅应用镜像），代码更新时使用，几秒钟完成"
    echo "  start   启动服务"
    echo "  stop    停止服务"
    echo "  restart 重启服务（快速构建 + 启动）"
    echo "  logs    查看日志"
    echo ""
    echo "构建模式 (环境变量 BUILD_MODE):"
    echo "  dev   - 开发模式: 使用本地代码 (默认)"
    echo "  prod  - 生产模式: 从 GitHub 克隆最新代码"
    echo ""
    echo "示例:"
    echo "  ./build.sh full                # 首次构建 (开发模式)"
    echo "  ./build.sh quick               # 代码更新后快速构建 (开发模式)"
    echo "  BUILD_MODE=prod ./build.sh quick  # 生产模式构建 (从GitHub克隆)"
    echo "  ./build.sh restart             # 重启服务"
}

# 主逻辑
case "${1:-}" in
    full)
        log_info "当前构建模式: $BUILD_MODE"
        build_base
        build_app
        start
        ;;
    quick)
        log_info "当前构建模式: $BUILD_MODE"
        if ! check_base_image; then
            log_warn "基础镜像不存在，先执行完整构建..."
            build_base
        fi
        build_app
        start
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        build_app
        start
        ;;
    logs)
        logs
        ;;
    *)
        usage
        exit 1
        ;;
esac
