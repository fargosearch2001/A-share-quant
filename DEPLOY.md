# A股量化回测系统部署指南

本文档介绍如何将本项目部署到云服务器（如阿里云、腾讯云、AWS 等）。

## 推荐方式：Docker 容器化部署

这是最简单、最稳定的部署方式，无需在服务器上配置复杂的 Python 环境。

### 1. 准备工作

确保您的云服务器已经安装了 `Docker` 和 `docker-compose`。

如果未安装，可以使用以下命令一键安装（以 Ubuntu 为例）：

```bash
# 更新 apt
sudo apt-get update

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
sudo apt-get install -y docker-compose
```

### 2. 获取代码

在服务器上克隆您的代码仓库：

> **⚠️ 注意**：如果您使用的是国内（内地）服务器，直接访问 GitHub 可能会失败或非常慢。
> 推荐使用 GitHub 镜像代理地址（如 `https://gitclone.com/` 或 `https://ghproxy.com/`）进行加速：

```bash
# 原地址
# git clone https://github.com/您的用户名/A-share-quant.git

# 使用镜像加速 (示例)
git clone https://gitclone.com/github.com/fargosearch2001/A-share-quant.git
cd A-share-quant
```

或者，您可以先将代码下载到本地电脑，然后通过 SFTP 工具（如 FileZilla）上传到服务器。

### 3. 一键启动

在项目根目录下运行：

```bash
# 构建镜像并后台启动
sudo docker-compose up -d
```

等待几分钟构建完成后，您可以通过浏览器访问：

```
http://<您的服务器公网IP>:8501
```

### 4. 常用管理命令

```bash
# 查看容器状态
sudo docker-compose ps

# 查看日志
sudo docker-compose logs -f

# 停止服务
sudo docker-compose down

# 更新代码后重新部署
git pull
sudo docker-compose up -d --build
```

---

## 备选方式：传统 Python 环境部署

如果您不想使用 Docker，也可以直接在服务器上运行。

### 1. 安装 Python 3.10+

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
```

### 2. 获取代码并配置环境

```bash
git clone https://github.com/您的用户名/A-share-quant.git
cd A-share-quant

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 后台启动

推荐使用 `nohup` 让其在后台运行：

```bash
nohup streamlit run src/web/app.py --server.port 8501 > web.log 2>&1 &
```

访问方式同上。
