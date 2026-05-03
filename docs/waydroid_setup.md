# Waydroid Setup Guide

## 1. 安装 Waydroid（Ubuntu 22.04）

```bash
curl -s https://repo.waydro.id/waydroid.gpg | sudo tee /usr/share/keyrings/waydroid.gpg > /dev/null
echo 'deb [signed-by=/usr/share/keyrings/waydroid.gpg] https://repo.waydro.id/ jammy main' | sudo tee /etc/apt/sources.list.d/waydroid.list
sudo apt update && sudo apt install waydroid
```

## 2. 初始化（选 GAPPS 镜像以获得 Play Store，或选 VANILLA）

```bash
sudo waydroid init -s GAPPS
```

## 3. 启动 Session

```bash
waydroid session start
```

检查状态：

```bash
waydroid status
# Session: RUNNING
# Container: RUNNING  ← 若显示 FROZEN，运行 waydroid show-full-ui 解冻
```

若容器处于 FROZEN 状态，ADB 无法连接，需先解冻：

```bash
waydroid show-full-ui
```

## 4. 安装 ARM 转译层（libndk）

Waydroid 默认运行 x86_64 镜像，无法直接安装 ARM/ARM64 APK（微信只提供 ARM 版本）。需先安装 ARM 转译：

```bash
# 在项目根目录执行
python3 -m venv .venv
git clone https://github.com/casualsnek/waydroid_script .venv/waydroid_script
.venv/bin/pip install -r .venv/waydroid_script/requirements.txt
cd .venv/waydroid_script
sudo ../.venv/bin/python3 main.py install libndk
```

验证转译已启用：

```bash
adb -s 192.168.240.112:5555 shell getprop ro.dalvik.vm.native.bridge
# 应返回非 0 的值
```

安装完成后重启 Waydroid：

```bash
waydroid session stop
waydroid session start
```

## 5. 连接 ADB

Waydroid 容器的 IP 地址查看方式：

```bash
waydroid status
# IP address: 192.168.240.112  ← 使用此 IP，非网桥 IP 192.168.240.1
```

连接 ADB：

```bash
adb connect 192.168.240.112:5555
# 若提示 unauthorized，在 Waydroid UI 弹窗中点击 Allow
```

验证连接：

```bash
adb devices
# List of devices attached
# 192.168.240.112:5555   device
```

查询设备 ABI（用于确认安装正确的 APK 架构）：

```bash
adb -s 192.168.240.112:5555 shell getprop ro.product.cpu.abi
# x86_64
```

## 6. 安装微信 APK

从微信官网下载 ARM64 版本 APK，然后安装（libndk 转译层会处理 ARM→x86_64）：

```bash
adb install -r ~/Downloads/weixin8070android3060_0x28004634_arm64_1.apk
# Performing Streamed Install
# Success
```

> **注意**：需先完成步骤 4（安装 libndk），否则会报 `INSTALL_FAILED_NO_MATCHING_ABIS`。

## 7. 手动登录微信（只需一次）

在 Waydroid 界面中手动完成微信登录。

## 8. 安装 WechatBridge APK

```bash
cd apk && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## 9. 启用 Accessibility Service

```bash
adb shell settings put secure enabled_accessibility_services com.wechatbridge/.WechatAccessibilityService
adb shell settings put secure accessibility_enabled 1
```

## 10. 建立 Port Forward

```bash
bash scripts/setup_adb_forward.sh
```

## 完成验证

```bash
make health
```

---

## 微信登录问题排查

### 背景

项目目标：在 Waydroid (Linux x86_64) 上运行新版微信（个人账号），通过 Accessibility Service 实现 WeChat Bot 加入群聊。

微信对模拟器环境有严格的风控检测，以下方法均已测试。

### 已尝试的方法

| 方法 | 结果 | 原因 |
|------|------|------|
| 短信验证码登录 | 收不到验证码 | 微信检测到模拟器，拦截短信下发 |
| 伪造设备属性（Pixel 6）| 登录转圈超时 | 微信风控不只依赖 `ro.product.*` 属性 |
| `ro.build.characteristics=nosdcard` | 无效 | 微信 tablet 判断有独立逻辑 |
| 修改屏幕分辨率为手机比例 | 无效 | 仍显示 "Log in on Tablet Only" |
| Email + 密码登录（国际版账号）| 转圈超时 | 模拟器环境被风控拦截请求 |
| ADB backup/restore | 不可行 | 微信设置 `allowBackup=false` |

### 下一步方向

#### 方向 1：真实手机登录后迁移数据（推荐）

成功率最高，对微信版本无限制。

1. 准备一台 root 过的 Android 手机，安装 Magisk + Shamiko 隐藏 root
2. 在手机上正常登录微信
3. 通过 ADB 导出登录数据：
   ```bash
   adb -s <手机ID> shell "su -c 'tar -czf /sdcard/wechat_data.tar.gz /data/data/com.tencent.mm'"
   adb -s <手机ID> pull /sdcard/wechat_data.tar.gz
   ```
4. 推送到 Waydroid：
   ```bash
   adb -s 192.168.240.112:5555 push wechat_data.tar.gz /sdcard/
   adb -s 192.168.240.112:5555 shell "su -c 'tar -xzf /sdcard/wechat_data.tar.gz -C /'"
   ```

#### 方向 2：LSPosed + 反检测插件

在 Waydroid 内安装 Magisk → LSPosed → Shamiko，绕过微信模拟器检测。步骤较复杂，Waydroid 对 Magisk 支持不稳定。

#### 方向 3：VirtualXposed

不需要 root，相对简单，但长期未维护，对微信 8.x 兼容性存疑，不推荐。

---

## 常用命令速查

| 操作 | 命令 |
|------|------|
| 查看 Waydroid 状态 | `waydroid status` |
| 启动 session | `waydroid session start` |
| 停止 session | `waydroid session stop` |
| 解冻容器（显示 UI） | `waydroid show-full-ui` |
| 连接 ADB | `adb connect 192.168.240.112:5555` |
| 列出 ADB 设备 | `adb devices` |
| 重启 ADB server | `adb kill-server && adb start-server` |
| 查看容器 ABI | `adb -s 192.168.240.112:5555 shell getprop ro.product.cpu.abi` |
| 查看 ARM 转译状态 | `adb -s 192.168.240.112:5555 shell getprop ro.dalvik.vm.native.bridge` |
| 安装 APK | `adb install -r /path/to/app.apk` |
| 健康检查 | `make health` |
