# 真机方案：ADB + Python WeChat Bot

## 背景

Waydroid 模拟器方案因微信风控无法完成登录（详见 [waydroid_setup.md](waydroid_setup.md)）。
改为通过 USB 连接真实 Android 手机，微信在手机上运行，Python 通过 ADB 控制。

## 架构

```
Linux Host (x86_64)
│
│  Python Controller
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐
│  │  Scheduler   │  │ Event Listener│  │ Message Router  │
│  │ (APScheduler)│  │  (WebSocket)  │  │ (Rules Engine)  │
│  └──────┬───────┘  └──────┬────────┘  └────────┬────────┘
│         │                 │ 实时推送              │
│  ┌──────▼─────────────────┼──────────────────────▼──────┐
│  │            ADB Bridge (USB)                           │
│  │       adb shell / adb forward / uiautomator2         │
│  └───────────────────────┬──────────────────────────────┘
│                          │ USB
│         ┌────────────────▼────────────────┐
│         │      Android Phone               │
│         │                                 │
│         │  ┌─────────────┐  ┌──────────┐  │
│         │  │  WeChat APK │◄─│WechatBridge│ │
│         │  │(com.tencent │  │  APK     │  │
│         │  │    .mm)     │  │(Accessibility│
│         │  └─────────────┘  │ Service) │  │
│         │                   └──────────┘  │
│         └─────────────────────────────────┘
```

**数据流**：
- 上行（读消息）：微信收到消息 → Accessibility Service 捕获 → WebSocket 推送 → `adb forward` → Python
- 下行（发消息）：Python → ADB Bridge → `adb shell input` / uiautomator2 → 手机微信

## 准备工作清单

### 1. 手机端准备

- [ ] Android 手机一台（Android 8.0+，推荐 Android 10-13）
- [ ] 手机已登录微信（个人账号，加入目标群聊）
- [ ] 开启 USB 调试：设置 → 开发者选项 → USB 调试
- [ ] 允许 ADB 授权：连接 USB 后在手机弹窗点击"允许"
- [ ] 关闭手机自动锁屏（或设置超长锁屏时间）
- [ ] 保持微信在前台运行（防止后台省电杀进程）

验证连接：
```bash
adb devices
# R9TX9116YDA   device  ← 显示 device 而非 unauthorized
```

### 2. Linux 开发环境准备

- [ ] ADB 已安装：`adb version`
- [ ] Python 3.10+：`python3 --version`
- [ ] 项目依赖安装：`pip install -r requirements.txt`（或 `poetry install`）
- [ ] uiautomator2 安装到手机：`python3 -m uiautomator2 init`

### 3. WechatBridge APK 构建

- [ ] 安装 Android Studio 或 JDK 17 + Gradle
- [ ] 构建 APK：
  ```bash
  cd apk && ./gradlew assembleDebug
  ```
- [ ] 安装到手机：
  ```bash
  adb install -r app/build/outputs/apk/debug/app-debug.apk
  ```
- [ ] 启用 Accessibility Service：
  ```bash
  adb shell settings put secure enabled_accessibility_services \
    com.wechatbridge/.WechatAccessibilityService
  adb shell settings put secure accessibility_enabled 1
  ```

### 4. ADB Port Forward 配置

WechatBridge APK 内嵌 WebSocket Server（端口 8765），需要 forward 到宿主机：

```bash
bash scripts/setup_adb_forward.sh
# 等价于：adb forward tcp:8765 tcp:8765
```

验证：
```bash
adb forward --list
# <serial>  tcp:8765  tcp:8765
```

### 5. 代码适配（Waydroid → 真机）

真机方案与 Waydroid 方案的主要差异：

| 项目 | Waydroid 方案 | 真机方案 |
|------|--------------|---------|
| ADB 连接方式 | `adb connect 192.168.240.112:5555`（TCP） | `adb -s <serial>`（USB） |
| 设备 serial | IP:Port | 字母数字串（如 `R9TX9116YDA`） |
| waydroid_manager.py | 需要 | **不需要**，删除或跳过 |
| 微信保活 | 守护 Waydroid 容器 | 守护手机 WiFi/USB 连接 + 微信前台 |

需修改 `core/adb_bridge.py` 中的连接逻辑，支持 USB serial 模式。

### 6. 保活策略

| 风险 | 应对 |
|------|------|
| 手机锁屏 | `adb shell settings put system screen_off_timeout 2147483647` |
| 微信被后台杀死 | 每 30s 检测 `adb shell pidof com.tencent.mm`，失败则 `am start` 拉起 |
| USB 断开重连 | Python 监听 `adb devices`，断开后自动重新 forward |
| ADB 授权过期 | 手机开启"始终允许此电脑调试" |

### 7. 验证流程

```bash
# 1. 确认设备连接
adb devices

# 2. 确认微信运行
adb shell pidof com.tencent.mm

# 3. 确认 Accessibility Service 已启用
adb shell settings get secure enabled_accessibility_services

# 4. 启动 port forward
bash scripts/setup_adb_forward.sh

# 5. 运行健康检查
make health
```

## 与 Waydroid 方案的代码复用

以下模块可直接复用，无需修改：
- `core/ws_client.py` — WebSocket 客户端
- `core/wechat_sender.py` — 消息发送逻辑
- `listener/event_listener.py` — 事件处理
- `router/` — 消息路由和 Handler
- `scheduler/` — 定时任务
- `storage/` — SQLite 存储
- `config/` — 配置加载
- `api/server.py` — REST 接口

需要修改：
- `core/adb_bridge.py` — 连接方式从 TCP 改为 USB serial
- `core/waydroid_manager.py` — 不再需要，注释掉或设为 no-op
- `utils/session_guard.py` — 保活逻辑从 Waydroid 容器改为手机进程检测
