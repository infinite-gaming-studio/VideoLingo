# VideoLingo Cloud Native - Application Image
# 基于基础镜像，只包含项目代码，频繁更新
# Usage: docker build -f Dockerfile.app -t videolingo:latest .
#
# 构建模式说明 / Build Mode:
# - 开发模式 (Dev):   docker build --build-arg BUILD_MODE=dev -f Dockerfile.app -t videolingo:latest .
# - 生产模式 (Prod):  docker build --build-arg BUILD_MODE=prod -f Dockerfile.app -t videolingo:latest .
# - 默认: 生产模式 (从 GitHub 克隆)

FROM videolingo:base

# 构建参数：选择构建模式 / Build argument: select build mode
ARG BUILD_MODE=prod

# 设置工作目录 / Set working directory
WORKDIR /app

# 根据构建参数选择代码来源 / Select code source based on build mode
RUN if [ "$BUILD_MODE" = "dev" ]; then \
        echo "[DEV MODE] 使用本地代码 / Using local code"; \
    else \
        echo "[PROD MODE] 从 GitHub 克隆代码 / Cloning from GitHub"; \
        rm -rf ./* && git clone https://github.com/infinite-gaming-studio/VideoLingo.git .; \
    fi

# 开发模式下复制本地代码 / Copy local code in dev mode
COPY . .

# 环境变量配置 / Environment variables
ENV ANTHROPIC_API_KEY="" 
ENV OPENAI_API_KEY=""
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_MAX_UPLOAD_SIZE=2000
ENV CLOUD_NATIVE_MODE=true

# 暴露端口 / Expose port
EXPOSE 8501

# 健康检查 / Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# 启动命令 / Start command
CMD ["streamlit", "run", "st.py", "--server.port=8501", "--server.address=0.0.0.0"]
