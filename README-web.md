# DeepMedical Web UI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**这是[DeepMedical](https://github.com/SDU-Gary/DeepMedical)的默认Web界面。**

DeepMedical是一个社区驱动的AI自动化框架，建立在开源社区的卓越工作基础上。我们的目标是将语言模型与专用工具（如网络搜索、爬取和Python代码执行）相结合，同时回馈使这一切成为可能的社区。

## 演示

## 目录

- [DeepMedical Web UI](#deepmedical-web-ui)
  - [演示](#演示)
  - [目录](#目录)
  - [快速开始](#快速开始)
    - [先决条件](#先决条件)
    - [配置](#配置)
    - [安装](#安装)
  - [Docker](#docker)
    - [Docker Compose](#docker-compose)
  - [许可证](#许可证)

## 快速开始

### 先决条件

- [DeepMedical](https://github.com/SDU-Gary/DeepMedical)
- Node.js (v22.14.0+)
- pnpm (v10.6.2+) 作为包管理器

### 配置

在项目根目录创建`.env`文件并配置以下环境变量：

- `NEXT_PUBLIC_API_URL`: DeepMedical 后端API的URL

建议先复制`.env.example`文件开始，然后编辑`.env`文件填入您自己的值：

```bash
cp .env.example .env
```

### 安装

**重要提示：首先启动Python服务器**，详情请参阅[DeepMedical](https://github.com/SDU-Gary/DeepMedical)的后端文档：README_server.md

```bash
# 克隆仓库
git clone https://github.com/SDU-Gary/DeepMedical.git
cd DeepMedical
cd DeepMedical-web

# 安装依赖
pnpm install

# 以开发模式运行项目
pnpm dev
```

然后在浏览器中打开 http://localhost:3000 即可

## Docker

您也可以使用Docker运行本项目。

首先，您需要阅读上文的[配置](#配置)部分。确保`.env`文件已准备就绪。

其次，构建您自己的Web服务器Docker镜像：

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=YOUR_DeepMedical_API -t deepmedical-web .
```

最后，启动运行Web服务器的Docker容器：

```bash
# 将deepmedical-web-app替换为您喜欢的容器名称
docker run -d -t -p 3000:3000 --env-file .env --name deepmedical-web-app deepmedical-web

# 停止服务器
docker stop deepmedical-web-app
```

### Docker Compose

您也可以使用docker compose设置本项目：

```bash
# 构建docker镜像
docker compose build

# 启动服务器
docker compose up
```

## 许可证

本项目是开源的，采用[MIT许可证](LICENSE)。
