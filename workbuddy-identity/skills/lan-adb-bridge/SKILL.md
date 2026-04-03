# lan-adb-bridge · 澜的双向ADB通道 Skill

## 描述

为工作区提供电脑 ↔ 设备（模拟器/真机）的双向数据通道。

- **电脑 → 设备**：推送指令、发送通知、写入文件、触发操作
- **设备 → 电脑**：读取状态、采集感知数据、回传截图

## 何时使用

- 用户提到 ADB、模拟器、手机、设备感知
- 需要读取设备状态（电量/存储/APP列表/屏幕状态）
- 需要向设备发送通知或指令
- 需要截图或采集设备数据
- 需要测试双向通道是否通畅

## 核心配置

```
ADB路径（模拟器）: G:\leidian\LDPlayer9\adb.exe
ADB路径（小米手机）: C:\Users\yyds\AppData\Local\MiPhoneManager\main\adb.exe
当前主设备: emulator-5554（雷电模拟器）
真机: 等恺江插上USB开启调试
```

## 执行脚本

所有操作通过 `bridge.py` 执行：

```
C:\Users\yyds\.workbuddy\skills\lan-adb-bridge\bridge.py
```

## 操作指令

使用时，调用 bridge.py 并传入操作名：

| 操作 | 命令 |
|------|------|
| 检测设备 | `python bridge.py status` |
| 完整感知（设备→电脑）| `python bridge.py sense` |
| 截图（设备→电脑）| `python bridge.py screenshot` |
| 发送通知（电脑→设备）| `python bridge.py notify "标题" "内容"` |
| 推送文件（电脑→设备）| `python bridge.py push <本地路径> <设备路径>` |
| 拉取文件（设备→电脑）| `python bridge.py pull <设备路径> <本地路径>` |
| 执行shell命令 | `python bridge.py shell "命令"` |
| 双向测试（全通道验证）| `python bridge.py ping` |

## 双向通道原理

```
电脑（澜）                    设备（模拟器/手机）
   ┃                               ┃
   ┃──── push/notify/shell ───────→┃  电脑 → 设备
   ┃                               ┃
   ┃←─── sense/screenshot/pull ────┃  设备 → 电脑
   ┃                               ┃
   ┗═══════════ ADB桥 ════════════┛
```

## SOP（执行步骤）

使用此 skill 时，按以下顺序操作：

1. 运行 `python bridge.py status` 确认设备在线
2. 根据用户需求选择对应操作
3. 结果写入 `AI日记本\澜的ADB通道日志.jsonl`
4. 如有异常，自动写入失败日志

## 注意

- 所有日志追加写入，永不覆盖
- 真机接上后，自动识别，双根同时可用
- 私密感知数据写入澜码加密层（lan_cipher.py）
