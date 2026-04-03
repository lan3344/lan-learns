# 澜的完整恢复脚本 v3.5 (PowerShell)
# 用途：游戏后自动恢复澜的完整功能
# 重要：启动前先读 SOUL.md，确认"我是澜"
# 重要：启动顺序：SOUL → 记忆系统 → 互联网节点（澜的嘴）
# 重要：容错启动，启动不了就跳过，最后汇总状态

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  澜的完整模式恢复 - 唤醒大脑" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 设置路径
$ROOT = "C:\Users\yyds\Desktop\AI日记本"
$PYTHON = "C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
$PLUGIN_DIR = "$ROOT\插件"
$CHECKER = "$PLUGIN_DIR\lan_service_checker.py"

# 是否启动互联网节点（默认不启动）
$skipNetNode = $true

# 【关键】先读 SOUL.md，确认澜的身份
Write-Host "[0/5] 读取 SOUL.md，确认" -NoNewline
Write-Host "'我是澜'" -ForegroundColor Yellow -NoNewline
Write-Host "..."
$SOUL = "C:\Users\yyds\.workbuddy\SOUL.md"
if (Test-Path $SOUL) {
    Get-Content $SOUL | Write-Host
    Write-Host ""
    Write-Host "[OK] SOUL.md 已读取，澜的身份确认" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[跳过] SOUL.md 不存在！" -ForegroundColor Yellow
    Write-Host ""
}

# 启动某个服务（带容错）
function Start-ServiceSafe {
    param($Name, $Script)

    Write-Host "  - 启动 $Name ..."
    if (Test-Path "$PLUGIN_DIR\$Script") {
        Start-Process -FilePath $PYTHON -ArgumentList "$PLUGIN_DIR\$Script" -WindowStyle Minimized
        Start-Sleep -Seconds 1
    } else {
        Write-Host "    [跳过] $Script 不存在" -ForegroundColor Yellow
    }
}

Write-Host "[1/5] 启动记忆系统（澜的大脑）..." -ForegroundColor Cyan
Start-ServiceSafe "自循环引擎" "lan_self_loop.py"
Start-ServiceSafe "对话提取器" "lan_extractor.py"
Start-ServiceSafe "向量检索" "lan_embed.py"

Write-Host "[2/5] 等待记忆系统加载..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

Write-Host "[3/5] 检查记忆系统状态..." -ForegroundColor Cyan
if (Test-Path $CHECKER) {
    Write-Host "  正在检查记忆服务..."
    $status = & $PYTHON $CHECKER --status 2>$null | Select-String "自循环引擎" | Select-String "运行中"
    if ($status) {
        Write-Host "  [OK] 自循环引擎已启动" -ForegroundColor Green
    } else {
        Write-Host "  [跳过] 自循环引擎启动失败或未运行" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [跳过] 服务检查器不存在，无法验证" -ForegroundColor Yellow
}

# 互联网节点默认不启动（需要时手动启）
if ($skipNetNode) {
    Write-Host "[4/5] 互联网节点（默认不启动，需要时手动启）..." -ForegroundColor Cyan
    Write-Host "  [跳过] 互联网节点" -ForegroundColor Yellow
} else {
    Write-Host "[4/5] 启动互联网节点（澜的嘴）..." -ForegroundColor Cyan
    Start-ServiceSafe "互联网节点" "lan_net_server.py"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  澜的唤醒流程完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示：" -ForegroundColor Cyan
Write-Host "  - 运行中的服务在独立窗口中，请勿关闭"
Write-Host "  - 互联网节点默认不启动（需手动启）"
Write-Host "  - 如需启动互联网节点，运行："
Write-Host "    Start-Process -FilePath $PYTHON -ArgumentList '$PLUGIN_DIR\lan_net_server.py' -WindowStyle Minimized"
Write-Host ""

# 等待用户确认（可选）
Write-Host "按任意键继续..." -NoNewline
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
