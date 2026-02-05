#!/bin/bash
# VideoLingo Apple Silicon 环境检查脚本
# 用于验证 ARM64 部署环境是否就绪

set -e

echo "🔍 VideoLingo Apple Silicon 环境检查"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CHECK_PASSED=0
CHECK_WARNING=0
CHECK_FAILED=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECK_PASSED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECK_WARNING++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECK_FAILED++))
}

# 1. 检查操作系统
echo "📋 系统信息检查"
echo "---------------"

OS_TYPE=$(uname -s)
ARCH=$(uname -m)

echo "操作系统: $OS_TYPE"
echo "架构: $ARCH"

if [ "$OS_TYPE" = "Darwin" ]; then
    if [ "$ARCH" = "arm64" ]; then
        check_pass "检测到 Apple Silicon (ARM64)"
    else
        check_warn "检测到 Intel Mac，ARM64 优化可能不适用"
    fi
    
    # 检查 macOS 版本
    MACOS_VERSION=$(sw_vers -productVersion)
    echo "macOS 版本: $MACOS_VERSION"
    
    # 检查是否 >= 12.0
    MAJOR_VERSION=$(echo $MACOS_VERSION | cut -d. -f1)
    if [ "$MAJOR_VERSION" -ge 12 ]; then
        check_pass "macOS 版本符合要求 (>= 12.0)"
    else
        check_fail "macOS 版本过低，需要 >= 12.0 (Monterey)"
    fi
else
    check_warn "非 macOS 系统，ARM64 Docker 部署可能不适用"
fi

echo ""

# 2. 检查 Docker
echo "🐳 Docker 环境检查"
echo "------------------"

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo "Docker 版本: $DOCKER_VERSION"
    check_pass "Docker 已安装"
    
    # 检查 Docker Desktop
    if [ "$OS_TYPE" = "Darwin" ]; then
        if [ -d "/Applications/Docker.app" ]; then
            check_pass "Docker Desktop 已安装"
        else
            check_warn "未检测到 Docker Desktop 应用程序"
        fi
    fi
    
    # 检查 Docker 是否运行
    if docker info &> /dev/null; then
        check_pass "Docker 正在运行"
        
        # 检查 Docker 平台
        DOCKER_PLATFORM=$(docker system info --format '{{.Architecture}}')
        echo "Docker 平台: $DOCKER_PLATFORM"
        
        # 检查 Rosetta (对于 Apple Silicon)
        if [ "$OS_TYPE" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
            if docker system info 2>/dev/null | grep -q "Rosetta"; then
                check_pass "Rosetta 已启用"
            else
                check_warn "建议启用 Rosetta 以提高兼容性"
            fi
        fi
    else
        check_fail "Docker 未运行，请启动 Docker Desktop"
    fi
else
    check_fail "Docker 未安装"
    echo "  安装指南: https://docs.docker.com/desktop/install/mac-install/"
fi

echo ""

# 3. 检查 Docker Compose
echo "🐙 Docker Compose 检查"
echo "---------------------"

if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version --short)
    echo "Docker Compose 版本: $COMPOSE_VERSION"
    check_pass "Docker Compose 已安装"
elif docker-compose --version &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | sed 's/,//')
    echo "Docker Compose 版本: $COMPOSE_VERSION"
    check_pass "Docker Compose (旧版) 已安装"
else
    check_fail "Docker Compose 未安装"
fi

echo ""

# 4. 检查项目文件
echo "📁 项目文件检查"
echo "---------------"

if [ -f "docker-compose.yml" ]; then
    check_pass "docker-compose.yml 存在"
else
    check_fail "docker-compose.yml 不存在"
fi

if [ -f "Dockerfile.arm64" ]; then
    check_pass "Dockerfile.arm64 存在"
else
    check_fail "Dockerfile.arm64 不存在"
fi

if [ -f "requirements.arm64.txt" ]; then
    check_pass "requirements.arm64.txt 存在"
else
    check_fail "requirements.arm64.txt 不存在"
fi

if [ -f "deploy-arm64.sh" ]; then
    check_pass "deploy-arm64.sh 存在"
else
    check_warn "deploy-arm64.sh 不存在"
fi

echo ""

# 5. 检查系统资源
echo "💾 系统资源检查"
echo "---------------"

if [ "$OS_TYPE" = "Darwin" ]; then
    # 检查内存
    TOTAL_MEM=$(sysctl -n hw.memsize)
    TOTAL_MEM_GB=$((TOTAL_MEM / 1024 / 1024 / 1024))
    echo "总内存: ${TOTAL_MEM_GB}GB"
    
    if [ "$TOTAL_MEM_GB" -ge 16 ]; then
        check_pass "内存充足 (>= 16GB)"
    elif [ "$TOTAL_MEM_GB" -ge 8 ]; then
        check_warn "内存较少 (8-16GB)，可能影响性能"
    else
        check_fail "内存不足 (< 8GB)，建议升级"
    fi
    
    # 检查 CPU 核心数
    CPU_CORES=$(sysctl -n hw.ncpu)
    echo "CPU 核心数: $CPU_CORES"
    
    if [ "$CPU_CORES" -ge 8 ]; then
        check_pass "CPU 核心数充足 (>= 8)"
    else
        check_warn "CPU 核心数较少，可能影响性能"
    fi
    
    # 检查磁盘空间
    FREE_SPACE=$(df -h . | awk 'NR==2 {print $4}')
    echo "可用磁盘空间: $FREE_SPACE"
fi

echo ""

# 6. 网络连接检查
echo "🌐 网络连接检查"
echo "---------------"

echo "检查 GitHub 连接..."
if curl -s --max-time 5 https://github.com &> /dev/null; then
    check_pass "GitHub 可访问"
else
    check_warn "GitHub 连接缓慢或不可访问，可能影响构建"
fi

echo "检查 Docker Hub 连接..."
if curl -s --max-time 5 https://hub.docker.com &> /dev/null; then
    check_pass "Docker Hub 可访问"
else
    check_warn "Docker Hub 连接缓慢或不可访问，可能影响构建"
fi

echo ""

# 7. 端口检查
echo "🔌 端口检查"
echo "-----------"

if lsof -Pi :8501 -sTCP:LISTEN -t &> /dev/null; then
    check_warn "端口 8501 已被占用，可能需要修改端口映射"
else
    check_pass "端口 8501 可用"
fi

if lsof -Pi :8000 -sTCP:LISTEN -t &> /dev/null; then
    check_warn "端口 8000 已被占用，WhisperX 云端服务可能需要修改端口"
else
    check_pass "端口 8000 可用"
fi

echo ""

# 8. 总结
echo "======================================"
echo "📊 检查结果汇总"
echo "======================================"
echo -e "${GREEN}通过${NC}: $CHECK_PASSED"
echo -e "${YELLOW}警告${NC}: $CHECK_WARNING"
echo -e "${RED}失败${NC}: $CHECK_FAILED"
echo ""

if [ $CHECK_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 环境检查通过！可以开始部署 VideoLingo${NC}"
    echo ""
    echo "📖 下一步："
    echo "   1. 运行 ./deploy-arm64.sh 进行一键部署"
    echo "   2. 或运行 docker-compose build videolingo 手动构建"
    echo ""
    exit 0
else
    echo -e "${RED}❌ 环境检查未通过，请修复上述问题后再试${NC}"
    echo ""
    exit 1
fi
