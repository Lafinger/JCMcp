# 允许通过构建参数切换基础镜像；默认值保留为官方 Python 3.11 轻量镜像。
ARG BASE_IMAGE=python:3.11-slim
# 使用可配置的 Python 基础镜像构建当前服务，在 Docker Hub 受限时也可以切换到本地已有镜像。
FROM ${BASE_IMAGE}
# 将容器内的工作目录固定为 /app，后续文件复制和启动命令都在这里执行。
WORKDIR /app
# 在容器内创建独立虚拟环境，避免污染基础镜像已经存在的 Python 依赖。
RUN python -m venv /opt/venv
# 关闭 Python 标准输出缓冲，方便通过 docker logs 直接查看实时日志。
ENV PYTHONUNBUFFERED=1
# 关闭 pip 下载缓存，减少镜像构建后的体积。
ENV PIP_NO_CACHE_DIR=1
# 显式声明虚拟环境路径，便于后续命令和排障时复用。
ENV VIRTUAL_ENV=/opt/venv
# 将虚拟环境放到 PATH 前面，让容器默认使用这套隔离依赖。
ENV PATH="/opt/venv/bin:$PATH"
# 先复制依赖清单，便于利用 Docker 的层缓存提升重复构建速度。
COPY requirements.txt /app/requirements.txt
# 使用独立虚拟环境安装 unreal_controller_mcp.py 运行所需的 Python 依赖。
RUN pip install --upgrade pip && pip install -r /app/requirements.txt
# 将 MCP 服务脚本复制到容器工作目录中。
COPY unreal_controller_mcp.py /app/unreal_controller_mcp.py
# 暴露 MCP 的 streamable HTTP 服务端口。
EXPOSE 6565
# 暴露后台 WebSocket 控制端口。
EXPOSE 8765
# 为容器增加基础健康检查，只检查 6565 端口以避免对 WebSocket 服务产生无效握手日志。
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import socket; socket.create_connection(('127.0.0.1', 6565), 2).close()"
# 容器启动后直接运行 unreal_controller_mcp.py。
CMD ["python", "unreal_controller_mcp.py"]
