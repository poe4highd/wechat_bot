# WeChat Bot 开发计划

> 目标：在 Linux 机器上用 Waydroid + ADB + Python 搭建 WeChat Bot，无需实体手机。
> 日期：2026-04-17 | 最后更新：2026-04-17

---

## 一、整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      Linux Host (x86_64)                          │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                   Python Controller                        │   │
│  │                                                            │   │
│  │  ┌──────────┐   ┌───────────────┐   ┌──────────────────┐ │   │
│  │  │Scheduler │   │ Event Listener│   │  Message Router  │ │   │
│  │  │(APScheduler)  │(WebSocket/TCP)│   │  (Rules Engine)  │ │   │
│  │  └────┬─────┘   └───────┬───────┘   └────────┬─────────┘ │   │
│  │       │                 │ 实时推送              │           │   │
│  │  ┌────▼─────────────────┼────────────────────▼─────────┐ │   │
│  │  │              ADB Bridge（仅用于发送/控制）             │ │   │
│  │  │         adb shell am / input text / u2               │ │   │
│  │  └────────────────────────┬──────────────────────────── ┘ │   │
│  └──────────────────────────┬┼──────────────────────────────┘   │
│        ADB port forward      ││  WebSocket ws://localhost:8765    │
│  ┌───────────────────────────▼▼──────────────────────────────┐   │
│  │                Waydroid Container (Android 11)              │   │
│  │                                                            │   │
│  │  ┌─────────────────┐    ┌───────────────────────────────┐ │   │
│  │  │   WeChat APK    │◄───│   WechatBridge APK            │ │   │
│  │  │  (com.tencent   │    │   (Accessibility Service)     │ │   │
│  │  │   .mm)          │    │   • 监听消息事件（推送到Python）│ │   │
│  │  └─────────────────┘    │   • 内嵌 WebSocket Server     │ │   │
│  │                          │   • 执行发送指令               │ │   │
│  │                          └───────────────────────────────┘ │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────┐   ┌────────────────────────────────┐   │
│  │   SQLite             │   │  Config YAML / .env            │   │
│  │  (消息历史/发送日志)  │   │  (规则/定时/联系人列表)         │   │
│  └──────────────────────┘   └────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

**数据流**：
- 上行（读消息）：微信收到消息 → Accessibility Service 捕获事件 → WebSocket 推送 → Python 解析 → Router 匹配规则 → Handler 处理
- 下行（发消息）：Scheduler/Handler → ADB Bridge → `adb shell input` / uiautomator2 → Waydroid 微信

**为什么这样分工**：
- **读消息用 Accessibility Service**：事件驱动，实时推送，直接获取文本，无需 UI 轮询，不被版本更新破坏 resource-id
- **发消息用 ADB/uiautomator2**：uiautomator2 和 Accessibility Service **不能同时运行**（冲突），发送是单向操作，ADB 模拟输入足够稳定
- **通信用 WebSocket**：APK 内嵌 WebSocket Server（Java-WebSocket 库），`adb forward` 映射到宿主机端口，Python 长连接订阅消息事件

---

## 二、核心组件：WechatBridge APK

这是整个方案的关键，需要自己开发一个 Android APK。

### 功能职责
1. **Accessibility Service**：注册监听微信的 `AccessibilityEvent`，捕获消息文本、发送者、所属会话
2. **WebSocket Server**：内嵌 `java-websocket`，监听 `0.0.0.0:8765`，Python 通过 `adb forward` 连接
3. **指令执行器**（可选）：接收 Python 下发的发送指令，用 Accessibility API 填充输入框并点击发送（替代 uiautomator2）

### 消息事件 JSON 格式
```json
{
  "type": "message",
  "chat_id": "filehelper",
  "chat_name": "文件传输助手",
  "sender": "张三",
  "content": "你好",
  "ts": 1713340800,
  "is_group": false
}
```

### Android 13 Accessibility 权限问题
Waydroid 默认运行 Android 11，**不受** Android 13 的 sideload Accessibility 限制。安装后在设置中手动开启辅助功能即可，或通过 ADB 命令启用：
```bash
adb shell settings put secure enabled_accessibility_services \
  com.yourpkg.wechatbridge/.WechatAccessibilityService
```

### 参考实现
- [HuixiangDou 微信 Accessibility 方案](https://huixiangdou.readthedocs.io/zh-cn/latest/doc_add_wechat_accessibility.html)（已验证 WeChat 8.0.47~8.0.49）
- [duqian291902259/WechatHook](https://github.com/duqian291902259/WechatHook)（Accessibility + Xposed 双方案参考）

---

## 三、模块划分

| 模块 | 职责 |
|------|------|
| `apk/` | WechatBridge Android 项目（Gradle，Java/Kotlin） |
| `core/waydroid_manager.py` | Waydroid 启动、保活、崩溃重启 |
| `core/adb_bridge.py` | ADB 连接封装、port forward、send_message（发送专用） |
| `core/ws_client.py` | WebSocket 客户端，订阅 WechatBridge 消息事件 |
| `core/wechat_sender.py` | 发送消息：navigate + input + send（uiautomator2 或 ADB input） |
| `listener/event_listener.py` | 处理 WebSocket 推入的消息事件，入库、分发 Router |
| `router/message_router.py` | 规则匹配引擎 |
| `router/handlers/` | keyword / llm / echo Handler |
| `scheduler/task_scheduler.py` | APScheduler + SQLiteJobStore |
| `scheduler/push_task.py` | 定时推送任务 |
| `storage/db.py` | SQLite 操作封装 |
| `storage/models.py` | 数据模型 |
| `config/loader.py` | YAML/env 配置加载，watchdog 热重载 |
| `utils/session_guard.py` | 登录态守护，被踢告警 |
| `utils/retry.py` | 指数退避重试装饰器 |
| `api/server.py` | FastAPI REST 接口（手动触发/状态查询） |

---

## 四、关键技术选型

### 消息读取：Accessibility Service（主方案）

| 对比项 | UIAutomator 轮询（旧方案） | Accessibility Service（新方案） |
|--------|--------------------------|-------------------------------|
| 延迟 | 3-10s（轮询间隔） | <500ms（事件驱动） |
| 微信版本兼容性 | 弱（resource-id 随版本变） | 强（事件 API 稳定） |
| 消息完整性 | 可能遗漏（轮询间隔内多条） | 完整（每条消息独立事件） |
| CPU 占用 | 高（持续 UI dump） | 极低（事件回调） |
| 开发成本 | 低 | 中（需开发 APK） |
| 与 uiautomator2 兼容 | 冲突（不可同时运行） | 兼容（分工明确） |

### 消息发送：uiautomator2（发送专用）

uiautomator2 仅在需要发送消息时短暂启动，发送完成后释放控制权，避免与 Accessibility Service 冲突。

发送流程：
1. 检查当前微信界面（截图/UI dump 确认）
2. 通过搜索导航到目标聊天
3. `d(resourceId=INPUT_BOX).set_text(msg)` → `d(resourceId=SEND_BTN).click()`
4. 确认发送成功后退出操作

**备选**：将发送逻辑也集成到 WechatBridge APK（Accessibility API 操作输入框），彻底去掉 uiautomator2 依赖。Phase 3 评估。

### Waydroid 保活

| 策略 | 实现 |
|------|------|
| systemd 自动重启 | waydroid session 封装为 systemd unit |
| Python 心跳 | 每 30s `adb shell echo ok`，失败触发重启 |
| 微信进程守护 | 检测 `com.tencent.mm` 不存在则 `am start` 拉起 |
| WebSocket 断线检测 | ws_client 断线 → 触发 APK 重启 + 重连 |
| 屏幕常亮 | `adb shell settings put system screen_off_timeout 2147483647` |

### 定时任务

**APScheduler**（cron / interval / date，SQLiteJobStore 持久化）

### 数据存储

| 用途 | 方案 |
|------|------|
| 消息历史/去重 | SQLite：`messages(id, chat_id, sender, content, ts, processed)` |
| 发送日志 | SQLite：`send_log(id, target, content, ts, status)` |
| APScheduler 任务 | SQLiteJobStore |

---

## 五、开发阶段

### Phase 1：基础环境搭建（3-5 天）

**目标**：Waydroid 稳定运行微信，ADB 连通，Python 能截图和 dump UI

- [ ] 安装 Waydroid（LineageOS 镜像，含 libhoudini ARM→x86 转译层）
- [ ] 配置 Waydroid 网络（NAT 模式，微信能联网）
- [ ] 安装微信 ARM64 APK：`waydroid app install weixin.apk`
- [ ] 验证 ADB 连接：`adb connect 192.168.240.1:5555`
- [ ] 手动完成微信登录（扫码/手机号，仅操作一次）
- [ ] 配置屏幕常亮 + 勿扰模式
- [ ] 实现 `core/waydroid_manager.py`（start/stop/status/restart）
- [ ] 实现 `core/adb_bridge.py`（connect/shell/screenshot/forward）
- [ ] 编写 `systemd/wechat-bot.service`，配置 Waydroid 开机自启

**交付物**：Python 能连接 ADB、截图；Waydroid 开机自启

**风险预案**：
- 微信 ARM 包崩溃 → 尝试不同版本（8.0.47-8.0.49 已知可用），检查 libhoudini 是否正常
- ADB 连接不稳定 → `adb forward tcp:5555 tcp:5555` 用 localhost 连接

---

### Phase 2：开发 WechatBridge APK（7-10 天）

**目标**：APK 能实时捕获微信消息并通过 WebSocket 推送给 Python

**Android APK 开发任务**：
- [ ] 创建 Android 项目（`apk/`，minSdk 28，targetSdk 30）
- [ ] 添加依赖：`java-websocket:1.5.x`（内嵌 WebSocket Server）
- [ ] 实现 `WechatAccessibilityService.java`：
  - 在 `AndroidManifest.xml` 声明服务和 `accessibility_service_config.xml`
  - `onAccessibilityEvent()` 过滤 `com.tencent.mm`
  - 提取 `TYPE_WINDOW_CONTENT_CHANGED` / `TYPE_VIEW_TEXT_CHANGED` 事件的消息文本
  - 解析 chat_id（会话标题）、sender（发送者名）、content（消息内容）
- [ ] 实现 `BridgeWebSocketServer.java`：
  - 监听 `0.0.0.0:8765`，广播消息 JSON 到所有连接的客户端
  - 心跳 ping/pong，断线重连支持
- [ ] 编译打包 APK，签名（debug keystore 即可）
- [ ] 安装到 Waydroid：`adb install -r wechat_bridge.apk`
- [ ] ADB 开启 Accessibility：`adb shell settings put secure enabled_accessibility_services ...`
- [ ] `adb forward tcp:8765 tcp:8765` 映射到宿主机

**Python 客户端任务**：
- [ ] 实现 `core/ws_client.py`（websockets 库，异步长连接，自动重连）
- [ ] 实现 `listener/event_listener.py`（解析消息 JSON，入库，调用 Router）
- [ ] 实现 `storage/db.py` + `storage/models.py`
- [ ] 端到端测试：发消息给微信，Python ws_client 收到事件并入库

**关键代码参考（APK 侧）**：
```java
// WechatAccessibilityService.java
@Override
public void onAccessibilityEvent(AccessibilityEvent event) {
    if (!"com.tencent.mm".equals(event.getPackageName())) return;
    if (event.getEventType() != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) return;

    String chatName = getCurrentChatTitle();
    List<CharSequence> texts = event.getText();
    if (texts.isEmpty()) return;

    JSONObject msg = new JSONObject();
    msg.put("type", "message");
    msg.put("chat_name", chatName);
    msg.put("content", texts.get(0).toString());
    msg.put("ts", System.currentTimeMillis() / 1000);
    server.broadcast(msg.toString());
}
```

**关键代码参考（Python 侧）**：
```python
# core/ws_client.py
async def listen():
    async for ws in websockets.connect("ws://localhost:8765"):
        async for raw in ws:
            event = json.loads(raw)
            await event_listener.handle(event)
```

**交付物**：APK 安装运行，Python 实时收到微信消息事件

---

### Phase 3：发送 + 路由 + 定时推送（5-7 天）

**目标**：Bot 能自动回复，能按计划定时发送

**消息发送**：
- [ ] 实现 `core/wechat_sender.py`（uiautomator2，发送专用）：
  - `send_to(contact_name, text)` 搜索导航 + 输入 + 发送
  - 发送前检查当前界面状态，避免与 Accessibility Service 冲突
  - 加互斥锁（同时只允许一个发送操作）
- [ ] 测试发送到私聊 / 群聊的完整流程

**自动回复**：
- [ ] 实现 `router/message_router.py`（关键词/正则匹配）
- [ ] 实现 `router/handlers/keyword_handler.py`
- [ ] 实现 `router/handlers/llm_handler.py`（调用 Claude API，`httpx` 异步）
- [ ] 实现 `router/handlers/echo_handler.py`（调试用）
- [ ] 设计 `config/rules.yaml` + `config/loader.py`（watchdog 热重载）

**定时推送**：
- [ ] 实现 `scheduler/task_scheduler.py`（APScheduler + SQLiteJobStore）
- [ ] 实现 `scheduler/push_task.py`（Jinja2 模板渲染 + 调用 wechat_sender）
- [ ] 设计 `config/schedule.yaml`
- [ ] CLI：`python -m wechat_bot schedule add/list/remove`

**可选评估**：将发送逻辑集成进 WechatBridge APK，彻底去掉 uiautomator2

**配置格式**：
```yaml
# rules.yaml
rules:
  - name: "智能问答"
    match: {type: regex, pattern: "^@Bot (.+)"}
    handler: llm
    cooldown_seconds: 10
    scope: ["群A", "群B"]   # 留空表示所有会话

# schedule.yaml
tasks:
  - name: "每日早报"
    cron: "0 8 * * *"
    targets:
      - {type: group, name: "团队群"}
    content_template: "templates/morning_news.jinja2"
    enabled: true
```

**交付物**：完整自动回复 + 定时推送

---

### Phase 4：稳定性加固与运维（3-5 天）

**目标**：7×24 无人值守，崩溃自动恢复

**稳定性**：
- [ ] 完整崩溃检测 + 重启序列：
  - ADB 心跳 → 微信进程 → WebSocket 可连 → 登录态正常
  - 重启序列：stop session → start → 等待 boot → 拉起微信 → 启动 APK → 重建 port forward
- [ ] 微信登录态检测（识别登录页/被踢弹窗），被踢后告警不自动重登
- [ ] 发送失败指数退避重试（`tenacity`，最多 3 次）
- [ ] WebSocket 断线自动重连（指数退避，上限 60s）
- [ ] 全局异常捕获，保障主循环不退出

**监控与日志**：
- [ ] loguru 结构化日志，按天滚动，ERROR 级别单独文件
- [ ] `api/server.py`（FastAPI）：
  - `POST /send` 手动触发发送
  - `GET /status` Bot 运行状态 + WebSocket 连接状态
  - `GET /stats` 消息收发统计

**运维工具**：
- [ ] `scripts/install.sh`（安装依赖、配置 systemd、首次 adb forward）
- [ ] `scripts/health_check.sh`（一键检查所有组件状态）
- [ ] `Makefile`（start/stop/restart/logs/status/install-apk）

**交付物**：72h+ 无人值守；崩溃 2 分钟内自动恢复

---

## 六、风险点与规避

| 风险 | 严重度 | 规避策略 |
|------|--------|----------|
| 微信检测模拟器封号 | 高 | ARM64 原版 APK + libhoudini；操作间隔 >1s；先用小号测试 |
| Waydroid 内核兼容性 | 高 | 锁定内核 5.15 LTS；优先 Ubuntu 22.04 宿主 |
| Accessibility 无法捕获所有消息类型 | 中 | 对比 HuixiangDou 方案抓取策略；对群消息、语音消息单独处理 |
| 微信 UI 变化导致 Accessibility 事件结构变 | 中 | 锁定微信版本（8.0.47-8.0.49 已验证）；不轻易升级 |
| 微信登录被踢（多设备检测） | 高 | 不同时登录手机；被踢立即人工告警，不自动重登 |
| ADB port forward 重启后丢失 | 中 | systemd ExecStartPost 每次重启后重建 forward |
| 发送与 Accessibility Service 冲突 | 中 | 发送时加互斥锁；发送完立即释放 |
| APK Accessibility 权限在升级 Android 版本后丢失 | 低 | 锁定 Waydroid 镜像版本；重启后脚本自动检查并重授权 |

---

## 七、目录结构

```
wechat_bot/
├── apk/                           # WechatBridge Android 项目
│   ├── app/src/main/java/.../
│   │   ├── WechatAccessibilityService.java
│   │   └── BridgeWebSocketServer.java
│   ├── app/src/main/res/xml/
│   │   └── accessibility_service_config.xml
│   └── build.gradle
├── config/
│   ├── settings.yaml              # ADB 地址、WebSocket 端口、轮询间隔
│   ├── rules.yaml                 # 消息回复规则
│   ├── schedule.yaml              # 定时任务
│   ├── contacts.yaml              # 联系人/群名单
│   └── loader.py
├── core/
│   ├── waydroid_manager.py
│   ├── adb_bridge.py              # ADB 封装（含 port forward）
│   ├── ws_client.py               # WebSocket 客户端（订阅消息）
│   └── wechat_sender.py           # 发送专用（uiautomator2）
├── listener/
│   └── event_listener.py          # 处理 WebSocket 推入事件
├── router/
│   ├── message_router.py
│   └── handlers/
│       ├── base_handler.py
│       ├── keyword_handler.py
│       ├── llm_handler.py
│       └── echo_handler.py
├── scheduler/
│   ├── task_scheduler.py
│   └── push_task.py
├── storage/
│   ├── db.py
│   ├── models.py
│   └── state_manager.py
├── utils/
│   ├── session_guard.py
│   ├── retry.py
│   └── logger.py
├── api/
│   └── server.py
├── templates/
│   └── morning_news.jinja2
├── scripts/
│   ├── install.sh
│   ├── health_check.sh
│   └── setup_adb_forward.sh       # 新增：重建 port forward
├── systemd/
│   └── wechat-bot.service
├── tests/
│   └── fixtures/
│       └── accessibility_event_sample.json  # 替换为 Accessibility 事件样本
├── data/
├── docs/
│   ├── PLAN.md
│   ├── INSTALL.md
│   ├── WAYDROID_SETUP.md
│   ├── APK_BUILD.md               # 新增：WechatBridge APK 编译指南
│   └── TROUBLESHOOTING.md
├── .env.example
├── pyproject.toml
├── Makefile
└── README.md
```

---

## 八、依赖清单

```toml
[tool.poetry.dependencies]
python = "^3.11"

# WebSocket 客户端
websockets = "^12.0"

# 发送专用（uiautomator2）
uiautomator2 = "^2.16"
adbutils = "^2.7"

# 定时任务
apscheduler = "^3.10"
SQLAlchemy = "^2.0"

# 配置与模板
PyYAML = "^6.0"
Jinja2 = "^3.1"
python-dotenv = "^1.0"
watchdog = "^4.0"

# Web API
fastapi = "^0.115"
uvicorn = "^0.30"

# 工具
loguru = "^0.7"
httpx = "^0.27"
tenacity = "^8.3"

# LLM
anthropic = "^0.34"
```

**APK 侧依赖（build.gradle）**：
```gradle
implementation 'org.java-websocket:Java-WebSocket:1.5.4'
```

---

## 九、时间线

```
Week 1   Phase 1  环境搭建 + ADB 基础连通
Week 2-3 Phase 2  WechatBridge APK 开发 + WebSocket 联调
Week 4   Phase 3  发送 + 自动回复 + 定时推送
Week 5   Phase 4  稳定性加固 + 运维工具
```

**MVP 检查点**（Phase 2 结束）：
- Python 通过 WebSocket 实时收到微信消息（延迟 <1s）
- Python 能向指定联系人/群发送文本消息
- 整体运行 1 小时不崩溃

**完整版检查点**（Phase 4 结束）：
- 无人值守运行 72h+
- 消息自动回复延迟 <2s（事件驱动，远优于轮询方案）
- 定时推送零遗漏
- 崩溃后 2 分钟内自动恢复
