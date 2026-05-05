# 开发测试日志

## 环境信息

- Linux Host: Ubuntu 22.04, x86_64
- 手机: Samsung SM-A146U (Galaxy A14 5G)
- Android: 14 (SDK 34)
- ADB Serial: R9TX9116YDA
- 连接方式: USB

---

## 2026-04-19 — 初始环境检查

### 设备状态

| 项目 | 状态 | 说明 |
|------|------|------|
| ADB 连接 | ✅ | `R9TX9116YDA device` |
| 微信 (com.tencent.mm) | ✅ 运行中 | PID 13930 |
| WechatBridge APK | ⚠️ 已安装 | 包名 `com.wechat.listener`，非预期的 `com.wechatbridge` |
| Accessibility Service | ✅ 已启用 | `com.wechat.listener/.WeChatListenerService` |
| ADB Port Forward | ❌ 未配置 | 需要 `adb forward tcp:8765 tcp:8765` |

### 发现问题

1. **WechatBridge 包名不一致**：手机上安装的是 `com.wechat.listener`，项目 APK 源码包名为 `com.wechatbridge`。需确认手机上的版本是否为本项目构建的 APK。
2. **Port Forward 未建立**：WebSocket 通信尚未配置。
3. **WechatBridge WebSocket 状态未知**：需测试 8765 端口是否在监听。

### 深入检查结果

**手机上的 `com.wechat.listener`**：
- 2026-04-21 通过 `adb install` 安装，非本项目 APK
- 监听 8765 端口，但协议未知（接受 TCP 连接但无响应，不是标准 WebSocket）
- Accessibility Service 已启用：`com.wechat.listener/.WeChatListenerService`

**本项目 APK（`com.wechatbridge`）**：
- 源码在 `apk/` 目录，使用标准 WebSocket（`org.java_websocket`）
- 需构建后安装到手机
- `apk/gradlew` 不存在，需初始化 Gradle Wrapper

**Python 环境**：
- 项目 `.venv` 已安装：`websockets 16.0`, `uiautomator2 3.5.0`, `adbutils 2.12.0`

### 下一步

- [ ] 初始化 Gradle Wrapper（需要 Android SDK）
- [ ] 构建并安装本项目 `com.wechatbridge` APK
- [ ] 卸载 `com.wechat.listener`（或保留共存）
- [ ] 建立 port forward `tcp:8765 tcp:8765`
- [ ] 测试 WebSocket 连通性（Python ↔ APK）
- [ ] 测试消息读取（Accessibility → WebSocket → Python）
- [ ] 测试消息发送（Python → ADB → 微信）

---

## 2026-04-19 — APK 构建与安装

### Android SDK 路径问题

Android SDK 已安装在 `~/android-sdk/`，但系统 `$ANDROID_HOME` 未设置，导致 gradle 找不到。
构建时需显式指定：

```bash
ANDROID_HOME=~/android-sdk ./gradlew assembleDebug
```

建议永久设置（加入 `~/.bashrc`）：
```bash
export ANDROID_HOME=~/android-sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin
```

Gradle Wrapper 也不存在，手动创建步骤：
1. 创建 `apk/gradle/wrapper/gradle-wrapper.properties`
2. 从 GitHub 下载 `gradlew`、`gradle-wrapper.jar`

### APK 构建结果

```
BUILD SUCCESSFUL in 45s
输出: apk/app/build/outputs/apk/debug/app-debug.apk
```

### 安装到手机

Samsung 设备有 Play Protect 验证拦截，需先禁用：

```bash
adb -s R9TX9116YDA shell settings put global package_verifier_enable 0
adb -s R9TX9116YDA install -r app/build/outputs/apk/debug/app-debug.apk
```

### 连通性测试结果

| 项目 | 状态 | 说明 |
|------|------|------|
| WechatBridge APK 安装 | ✅ | `com.wechatbridge` 已安装 |
| Accessibility Service | ✅ | `com.wechatbridge/.WechatAccessibilityService` |
| ADB Port Forward | ✅ | `tcp:8765 → tcp:8765` |
| WebSocket 连接 | ✅ | Python 可连接 `ws://localhost:8765` |
| 消息接收 | ⏳ 待测试 | 需在微信聊天界面触发事件 |

### 下一步

- [ ] 在微信中发送消息，验证 Accessibility 事件能推送到 Python
- [ ] 测试消息发送（Python → ADB → 微信输入框）
- [ ] 验证 resource-id（`b7z`, `b7w`, `b83`, `j7`）是否匹配当前微信版本
- [ ] 实现 `core/adb_bridge.py` USB serial 模式适配

---

<!-- 新的测试记录追加在此处 -->
