# VideoLingo Cloud Native - Application Image
# 基于基础镜像，只包含项目代码，频繁更新
# Usage: docker build -f Dockerfile.app -t videolingo:latest .

FROM videolingo:base

# 设置工作目录 / Set working directory
WORKDIR /app

# 复制项目代码 / Copy project code
COPY . /app

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
