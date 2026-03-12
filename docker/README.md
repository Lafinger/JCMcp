# Docker 部署说明

## 1. 文件位置

当前项目的 Docker 相关文件都放在 `docker` 目录下：

- `docker/Dockerfile`
- `docker/docker-compose.yml`
- `docker/Dockerfile.dockerignore`
- `docker/README.md`

其中：

- `docker/Dockerfile` 用于构建运行 `unreal_controller_mcp.py` 的镜像。
- `docker/docker-compose.yml` 用于一键启动容器。
- `docker/Dockerfile.dockerignore` 用于减少镜像构建时传入 Docker 的无关文件。

## 2. 部署目标

本部署方案会把项目根目录下的 `unreal_controller_mcp.py` 打包进容器，并在容器内直接执行：

```powershell
python unreal_controller_mcp.py
```

容器启动后会暴露两个端口：

- `6565`：MCP 的 Streamable HTTP 服务端口。
- `8765`：后台 WebSocket 控制端口。

## 3. 前置要求

在 Windows 11 上部署前，请先确认：

1. 已安装并启动 Docker Desktop。
2. Docker Desktop 使用的是 Linux 容器模式。
3. 当前终端使用的是 PowerShell。
4. 当前项目源码位于本地，例如：`E:\AI\JCMcp`。

可以先执行下面的命令确认 Docker 可用：

```powershell
docker --version
docker compose version
```

## 4. 基础镜像说明

`docker/docker-compose.yml` 中已经预留了 `BASE_IMAGE` 构建参数。

当前默认值是：

```text
ghcr.nju.edu.cn/xinnan-tech/mcp-endpoint-server:latest
```

这样配置的原因是：当前环境已经验证可以直接用它完成构建。

如果你的机器可以正常访问 Docker Hub，推荐改用官方 Python 3.11 镜像。执行部署前，在 PowerShell 中先设置：

```powershell
$env:BASE_IMAGE = "python:3.11-slim"
```

如果你有自己的私有基础镜像，也可以改成你自己的镜像地址：

```powershell
$env:BASE_IMAGE = "your-registry/your-python-image:tag"
```

如果不设置 `BASE_IMAGE`，就会使用 `docker/docker-compose.yml` 里写好的默认值。

## 5. 进入项目目录

建议先进入项目根目录：

```powershell
Set-Location E:\AI\JCMcp
```

后续所有命令都以项目根目录为执行位置。

## 6. 构建并启动容器

在项目根目录执行：

```powershell
docker compose -f .\docker\docker-compose.yml up -d --build
```

这条命令会完成以下动作：

1. 使用 `docker/docker-compose.yml` 读取部署配置。
2. 根据 `docker/Dockerfile` 构建镜像。
3. 将 `requirements.txt` 和 `unreal_controller_mcp.py` 打包进镜像。
4. 创建并启动容器 `jcmcp-unreal-controller-mcp`。
5. 将宿主机端口 `6565` 和 `8765` 映射到容器内对应端口。

## 7. 查看容器状态

启动完成后，可以执行：

```powershell
docker compose -f .\docker\docker-compose.yml ps
```

如果状态显示类似下面这样，就表示容器已经正常运行：

```text
Up (healthy)
```

也可以直接查看容器列表：

```powershell
docker ps
```

## 8. 查看启动日志

如果你要确认服务是否已经真正启动，可以查看日志：

```powershell
docker logs -f jcmcp-unreal-controller-mcp
```

正常情况下，可以看到类似下面的信息：

```text
WebSocket control server listening on 0.0.0.0:8765
Uvicorn running on http://0.0.0.0:6565
```

这说明：

- WebSocket 控制服务已经监听 `8765`。
- MCP 的 HTTP 服务已经监听 `6565`。

## 9. 服务访问方式

容器启动后，宿主机可以通过下面的地址访问：

- MCP 端口：`http://127.0.0.1:6565`
- MCP 路径：`http://127.0.0.1:6565/mcp`
- WebSocket 端口：`ws://127.0.0.1:8765`

说明：

- `http://127.0.0.1:6565/mcp` 是当前服务实际可访问的 MCP 路径。
- 直接访问 `http://127.0.0.1:6565/` 返回 `404` 是正常现象。
- 直接用浏览器方式访问 `http://127.0.0.1:6565/mcp`，可能因为请求头不符合 MCP 协议而返回 `406`，这也是正常现象。

## 10. 常用运维命令

重新构建并启动：

```powershell
docker compose -f .\docker\docker-compose.yml up -d --build
```

只启动已有容器：

```powershell
docker compose -f .\docker\docker-compose.yml up -d
```

停止并删除容器、网络：

```powershell
docker compose -f .\docker\docker-compose.yml down
```

重启容器：

```powershell
docker compose -f .\docker\docker-compose.yml restart
```

查看容器详细状态：

```powershell
docker inspect jcmcp-unreal-controller-mcp
```

## 11. 修改代码后的重新部署

如果你修改了下面这些文件中的任意一个：

- `unreal_controller_mcp.py`
- `requirements.txt`
- `docker/Dockerfile`
- `docker/docker-compose.yml`

建议重新构建镜像并启动：

```powershell
docker compose -f .\docker\docker-compose.yml up -d --build
```

这样可以确保容器里的代码和依赖与你本地项目一致。

## 12. 端口占用处理

如果启动时报错端口被占用，通常是宿主机上的 `6565` 或 `8765` 已被其他程序使用。

你可以先查看占用情况：

```powershell
Get-NetTCPConnection -LocalPort 6565,8765 -ErrorAction SilentlyContinue
```

如果确实被占用，可以修改 `docker/docker-compose.yml` 里的端口映射，例如改成：

```yaml
ports:
  - "16565:6565"
  - "18765:8765"
```

修改后重新执行：

```powershell
docker compose -f .\docker\docker-compose.yml up -d --build
```

## 13. 构建失败的常见原因

### 13.1 无法拉取基础镜像

如果看到类似下面的错误：

```text
failed to authorize
failed to fetch anonymous token
```

通常说明当前网络无法访问默认镜像仓库。

处理方式：

1. 先尝试为 `BASE_IMAGE` 指定一个你本机能访问的镜像。
2. 或者切换到你自己的镜像仓库地址。
3. 然后重新执行构建命令。

示例：

```powershell
$env:BASE_IMAGE = "python:3.11-slim"
docker compose -f .\docker\docker-compose.yml up -d --build
```

### 13.2 依赖安装失败

如果是 `pip install` 阶段失败，通常与网络或依赖源有关。

处理方式：

1. 先确认容器构建期间可以联网。
2. 再确认 `requirements.txt` 中依赖版本有效。
3. 必要时为 `pip` 配置你自己的镜像源。

## 14. 健康检查说明

镜像内已经配置了健康检查，会定期检测容器内的 `6565` 端口是否可连接。

你可以通过下面命令查看健康状态：

```powershell
docker inspect --format "{{json .State.Health}}" jcmcp-unreal-controller-mcp
```

如果返回中包含：

```text
"Status":"healthy"
```

就表示容器当前运行正常。

## 15. 当前推荐的部署命令

如果你直接使用当前仓库中的 Docker 配置，最推荐的命令就是这一条：

```powershell
docker compose -f .\docker\docker-compose.yml up -d --build
```

如果你希望在执行前显式指定官方 Python 3.11 基础镜像，可以这样写：

```powershell
$env:BASE_IMAGE = "python:3.11-slim"
docker compose -f .\docker\docker-compose.yml up -d --build
```

## 16. 当前部署结果

这套 Docker 配置已经过本地验证，能够成功完成以下流程：

1. 构建镜像。
2. 启动容器。
3. 监听 `6565` 和 `8765`。
4. 健康检查通过。

如果你后面还想继续补充：

- 自动挂载源码目录用于开发热更新。
- 增加 `.env` 配置文件。
- 增加生产环境与开发环境两套 Compose 文件。

可以在当前 `docker` 目录结构上继续扩展。 
