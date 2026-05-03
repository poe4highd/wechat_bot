# GeweChat Docker 部署 WeChat Bot：可行性评估与开发方案

> 调研日期：2026-04-24  
> 项目路径：`/home/wcb/projects/wcbot`

---

## 1. GeweChat 概述

**GeweChat**（个微助手）是一个基于微信 iPad 协议的个人微信二次开发框架，通过 Docker 容器运行一个模拟 iPad 客户端的服务，对外暴露 RESTful API，让开发者用任意语言收发微信消息、管理联系人和群组。

### 工作原理

```
手机微信账号
    │ 扫码登录（iPad 协议）
    ▼
GeweChat Docker 容器
    ├── 端口 2531：REST API（发消息、查联系人等）
    └── 端口 2532：文件下载（图片、语音等）
    │
    │ HTTP 回调推送（消息事件）
    ▼
Bot 服务（Python / 任意语言）
    ├── 端口 9919：回调接收器
    └── 业务逻辑（AI 回复、定时任务等）
```

**协议层**：GeweChat 使用微信 iPad 协议（非桌面/Web 协议），登录后模拟 iPad 客户端与腾讯服务器保持连接。这一协议相对 Web 协议更稳定，但仍属非官方逆向工程。

---

## 2. 可行性评估

### 2.1 技术可行性

**优点：**
- Docker 一键部署，隔离环境，依赖清晰
- REST API 接口简洁，语言无关，调用门槛低
- 有官方 Python SDK `gewechat-client`（PyPI v0.1.5）
- 支持文本、图片、文件、语音、表情、小程序等消息类型
- 支持群组管理、联系人管理、自动回复等常用功能
- 社区有完整的集成案例（dify-on-wechat、AstrBot）

**缺点：**
- **项目已归档**（2025年5月3日，GitHub 仓库只读，停止维护）
- 依赖微信协议逆向，协议变更随时可能导致失效
- Docker 镜像仅托管在阿里云，来源可信度有限
- 需要 Docker 版本精确为 26.1.4，更高版本可能不兼容
- 服务器需与账号注册地同省（地理位置限制）
- 最低硬件要求：4核 CPU，8GB RAM

### 2.2 合规与封号风险

**风险等级：高**

微信《服务条款》和《可接受使用政策》明确禁止：
- 使用未经授权的第三方插件或自动化工具
- 使用非官方客户端或协议逆向工程工具

**常见封号触发行为：**
- 高频发送消息（尤其群发）
- 使用第三方 Hook 或模拟器
- 账号行为模式异常（机器人特征）

**参考：** GeweChat GitHub Issue #284 标题为"你们都不封号的吗"，说明封号是真实且普遍的问题。

### 2.3 方案对比

| 维度 | GeweChat | Wechaty | itchat/wxpy | 官方公众号 API | 当前 Waydroid 方案 |
|------|----------|---------|-------------|---------------|-------------------|
| **维护状态** | ⚠️ 已归档 | ✅ 活跃维护 | ❌ 已废弃 | ✅ 官方支持 | 🔨 自研 |
| **协议类型** | iPad 协议逆向 | 多协议（插件化） | Hook/Web 协议 | 官方 API | Accessibility 服务 |
| **Docker 支持** | ✅ 原生支持 | ✅ 支持 | ⚠️ 部分支持 | ✅ 无需特殊环境 | ❌ 需要 Waydroid |
| **个人账号** | ✅ 支持 | ✅ 支持 | ✅ 支持 | ❌ 需企业账号 | ✅ 支持 |
| **封号风险** | 🔴 高 | 🟡 中（取决于 puppet）| 🔴 高 | 🟢 无 | 🟡 中 |
| **消息类型** | 丰富 | 丰富 | 基础 | 受限（公众号格式）| 丰富 |
| **Python SDK** | ✅ 有 | ✅ 有 | ✅ 有 | ✅ 有 | 自研 |
| **上手难度** | 低 | 中 | 低 | 中 | 高 |
| **稳定性** | 🟡 中（协议易失效）| 🟡 中 | 🔴 低 | 🟢 高 | 🟡 中 |

### 2.4 综合结论

**可行，但有明确限制：**

> ✅ **适合**：个人项目、学习实验、内部小范围使用、快速原型验证  
> ❌ **不适合**：生产环境、商业用途、需要长期稳定运行的场景

GeweChat 提供了目前最低门槛的个人微信自动化方案之一，Docker 化部署和 REST API 设计使集成非常简便。但其已归档状态意味着任何微信协议更新都可能导致永久失效，且高封号风险是无法回避的约束。

---

## 3. 技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     服务器（Linux）                       │
│                                                          │
│  ┌──────────────────────┐    ┌──────────────────────┐   │
│  │   GeweChat 容器       │    │   Bot 服务（Python）  │   │
│  │                      │    │                      │   │
│  │  :2531 REST API  ────┼────► message_sender       │   │
│  │  :2532 文件下载   ────┼────► file_downloader     │   │
│  │                      │    │                      │   │
│  │  ← 回调推送 ──────────┼────  :9919 callback      │   │
│  │                      │    │  ├── message_router  │   │
│  └──────────────────────┘    │  ├── ai_client       │   │
│                               │  └── scheduler      │   │
│  ┌──────────────────────┐    └──────────────────────┘   │
│  │   数据持久化           │                               │
│  │  ./data/gewe/        │    ┌──────────────────────┐   │
│  │  ./data/bot/         │    │   Claude API（外部）   │   │
│  └──────────────────────┘    └──────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 端口规划

| 端口 | 服务 | 说明 |
|------|------|------|
| 2531 | GeweChat REST API | 发送消息、查询联系人、管理群组 |
| 2532 | GeweChat 文件服务 | 下载接收到的图片、语音等文件 |
| 9919 | Bot 回调接收器 | 接收 GeweChat 推送的消息事件 |

> **注意**：回调 URL 不能使用 `127.0.0.1` 或 `localhost`，必须使用服务器实际 IP。

### 3.3 数据流

**接收消息：**
```
微信用户发消息 → 腾讯服务器 → GeweChat 容器 → HTTP POST 到 :9919/callback → Bot 处理 → 调用 Claude API → 发送回复
```

**发送消息：**
```
Bot 服务 → POST :2531/v2/api/message/postText → GeweChat 容器 → 腾讯服务器 → 目标用户
```

---

## 4. Docker 部署方案

### 4.1 前置要求

- **系统**：Linux（Ubuntu 22.04 / Debian 12 推荐）
- **Docker**：推荐 26.1.4（更高版本可能导致服务启动失败）
- **硬件**：4核 CPU，8GB RAM，20GB 磁盘
- **网络**：服务器需能访问腾讯服务器（不能被限制出站流量）
- **账号**：一个已注册的微信个人账号（建议使用小号）

### 4.2 Docker 版本锁定

如果当前 Docker 版本过高，可以降级或使用 Docker 版本管理：

```bash
# 查看当前 Docker 版本
docker --version

# 如需降级到 26.1.4（Ubuntu）
apt-get remove docker-ce docker-ce-cli
apt-get install docker-ce=5:26.1.4-1~ubuntu.22.04~jammy \
                docker-ce-cli=5:26.1.4-1~ubuntu.22.04~jammy
```

### 4.3 目录结构

```
wcbot/
├── docker-compose.yml
├── .env
├── docs/
│   └── gewechat_docker_plan.md
├── data/
│   ├── gewe/          # GeweChat 数据持久化
│   └── bot/           # Bot 服务数据（SQLite、日志等）
└── bot/
    ├── main.py
    ├── callback.py
    ├── sender.py
    ├── ai_client.py
    └── requirements.txt
```

### 4.4 docker-compose.yml

```yaml
version: '3.8'

services:
  gewechat:
    image: registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest
    container_name: gewe
    volumes:
      - ./data/gewe:/root/temp
    ports:
      - "2531:2531"
      - "2532:2532"
    restart: unless-stopped
    privileged: true   # 标准镜像需要；Alpine 版镜像可去掉

  bot:
    build: ./bot
    container_name: wcbot
    environment:
      - GEWE_API_URL=http://gewe:2531/v2/api
      - CALLBACK_PORT=9919
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    ports:
      - "9919:9919"
    volumes:
      - ./data/bot:/app/data
    depends_on:
      - gewechat
    restart: unless-stopped
```

### 4.5 .env 文件

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
# 服务器实际 IP（用于回调 URL 注册）
SERVER_IP=192.168.1.100
```

### 4.6 部署命令

```bash
# 拉取镜像（国内服务器）
docker pull registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest
docker tag registry.cn-hangzhou.aliyuncs.com/gewe/gewe gewe

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f gewechat
docker compose logs -f bot

# 停止服务
docker compose down

# 验证 GeweChat API 是否正常
curl http://localhost:2531/v2/api/login/getLoginQrCode \
  -H "Content-Type: application/json" \
  -d '{"appId": ""}'
```

---

## 5. Python Bot 集成方案

### 5.1 安装依赖

```
# bot/requirements.txt
gewechat-client==0.1.5
anthropic>=0.40.0
fastapi>=0.115.0
uvicorn>=0.32.0
httpx>=0.27.0
pyyaml>=6.0
```

### 5.2 登录流程

```python
# bot/login.py
from gewechat_client import GewechatClient

def login(base_url: str, token: str) -> str:
    client = GewechatClient(base_url=base_url, token=token)
    
    # 生成登录二维码（打印到控制台）
    result = client.login(app_id="")
    app_id = result.get("appId")
    qr_url = result.get("qrImgBase64")  # Base64 二维码图片
    
    print(f"请扫码登录，app_id: {app_id}")
    # 保存 app_id 供后续使用
    return app_id
```

### 5.3 回调接收器

```python
# bot/callback.py
import os
from fastapi import FastAPI, Request
from sender import send_text
from ai_client import get_ai_reply

app = FastAPI()

@app.post("/v2/api/callback/collect")
async def handle_callback(request: Request):
    data = await request.json()
    
    msg_type = data.get("TypeName")
    if msg_type != "AddMsg":
        return {"status": "ignored"}
    
    msg = data.get("Msg", {})
    from_user = msg.get("FromUserName", {}).get("string", "")
    content = msg.get("Content", {}).get("string", "")
    app_id = data.get("Appid", "")
    
    # 过滤群消息（群 ID 以 @ 结尾）
    if from_user.endswith("@chatroom"):
        return {"status": "ignored"}
    
    # 获取 AI 回复并发送
    reply = await get_ai_reply(content)
    await send_text(app_id=app_id, wxid=from_user, message=reply)
    
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("CALLBACK_PORT", 9919)))
```

### 5.4 消息发送

```python
# bot/sender.py
import httpx
import os

GEWE_API_URL = os.getenv("GEWE_API_URL", "http://localhost:2531/v2/api")

async def send_text(app_id: str, wxid: str, message: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GEWE_API_URL}/message/postText",
            json={"appId": app_id, "toWxid": wxid, "content": message},
        )
        return resp.json()

async def send_image(app_id: str, wxid: str, image_url: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GEWE_API_URL}/message/postImage",
            json={"appId": app_id, "toWxid": wxid, "imgUrl": image_url},
        )
        return resp.json()
```

### 5.5 Claude AI 集成

```python
# bot/ai_client.py
import anthropic
import os

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def get_ai_reply(user_message: str) -> str:
    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="你是一个友善的微信助手，用简洁的中文回复用户消息。",
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text
```

### 5.6 注册回调 URL

启动 bot 服务后，需向 GeweChat 注册回调地址：

```python
# bot/setup.py
import httpx
import os

async def register_callback(app_id: str):
    server_ip = os.getenv("SERVER_IP", "127.0.0.1")
    callback_url = f"http://{server_ip}:9919/v2/api/callback/collect"
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{os.getenv('GEWE_API_URL')}/tools/setCallback",
            json={"appId": app_id, "callbackUrl": callback_url},
        )
        print(f"回调注册结果: {resp.json()}")
```

---

## 6. 与 wcbot 项目的集成建议

### 6.1 模块复用

当前 `/home/wcb/projects/wechat_bot/` 中已有可复用的模块：

| 现有模块 | 路径 | 复用方式 |
|---------|------|---------|
| 消息路由 | `router/message_router.py` | 直接复用规则匹配逻辑 |
| 定时任务 | `scheduler/task_scheduler.py` | 直接复用 APScheduler 配置 |
| 数据库模型 | `storage/db.py` + `models.py` | 复用 SQLite 存储层 |
| AI 客户端 | 集成在各模块 | 统一用 `anthropic` SDK |

### 6.2 建议配置结构

```yaml
# config/bot.yaml
gewe:
  api_url: "http://gewe:2531/v2/api"
  token: ""
  app_id: ""  # 首次登录后自动填充

callback:
  host: "0.0.0.0"
  port: 9919
  server_ip: "192.168.1.100"  # 用于注册回调 URL

rules:
  - pattern: "你好"
    response: "你好！有什么可以帮助你的？"
  - pattern: ".*"
    handler: "ai"   # 其余消息转 Claude 处理

schedule:
  - cron: "0 9 * * *"
    target_wxid: "wxid_xxxxx"
    message: "早安！"
```

---

## 7. 风险缓解措施

### 7.1 账号安全策略

- **使用专用小号**，不用主账号，避免重要联系人受影响
- **控制消息频率**：单用户每分钟不超过 5 条，每日不超过 200 条
- **避免群发**：群发行为是封号高危触发点
- **模拟人工延迟**：发送前随机等待 1-3 秒
- **监控登录状态**：检测到掉线立即停止自动发送，等待人工重新登录

### 7.2 降级方案

当 GeweChat 失效时（协议变更、项目失联），可快速切换至：

1. **Waydroid 方案**（`/home/wcb/projects/wechat_bot/`）：已有完整实现，切换成本低
2. **Wechaty + WechatFerry**：需安装 Windows 版微信，适合有 Windows 服务器的场景
3. **官方企业微信 API**：完全合规，功能受限但稳定

---

## 8. 替代方案推荐

### 8.1 Wechaty（推荐长期方案）

- **GitHub**：https://github.com/wechaty/wechaty（活跃维护，15k+ stars）
- **特点**：插件化设计，支持多种 puppet（WechatFerry、PadLocal 等）
- **Python SDK**：python-wechaty
- **适用场景**：需要长期稳定运行的项目

### 8.2 官方企业微信 API（推荐合规方案）

- 完全官方支持，零封号风险
- 需要企业主体注册
- 功能有限（无法操作个人账号）
- 适合：客服机器人、内部通知系统

### 8.3 继续现有 Waydroid 方案

- 已有完整架构（`/home/wcb/projects/wechat_bot/`）
- 基于 Android Accessibility Service，不依赖协议逆向
- 封号风险相对较低（行为更接近真实用户操作）
- 缺点：需要 Waydroid 环境，部署复杂度高

---

## 9. 快速启动检查清单

```
□ 服务器满足硬件要求（4核 8GB）
□ Docker 版本为 26.1.4
□ 端口 2531、2532、9919 未被占用
□ 服务器出站网络无限制
□ 准备好微信小号（不用主账号）
□ 获取 Anthropic API Key
□ 配置 .env 文件（SERVER_IP、ANTHROPIC_API_KEY）
□ docker compose up -d 启动服务
□ 调用登录 API，扫码登录
□ 注册回调 URL
□ 发送测试消息验证完整链路
```

---

*本文档基于 2026-04-24 的调研结果。GeweChat 项目已归档，建议定期评估是否需要切换到替代方案。*
