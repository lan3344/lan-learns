# ============================================================
#  澜的防火墙规则安装脚本
#  用途：阻止外网入站访问 LobsterAI(5175) 和 OpenClaw(18789)
#  运行方式：右键 -> 以管理员身份运行
#  原则：只防不攻，本机/局域网不受影响
# ============================================================

$rules = @(
    @{ Name="LAN-Guard-Block-5175";  Port=5175;  Desc="LobsterAI Vite界面" },
    @{ Name="LAN-Guard-Block-18789"; Port=18789; Desc="OpenClaw引擎网关" }
)

foreach ($r in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $r.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[已存在] $($r.Name) -- 跳过" -ForegroundColor Yellow
    } else {
        New-NetFirewallRule `
            -DisplayName $r.Name `
            -Direction Inbound `
            -Protocol TCP `
            -LocalPort $r.Port `
            -Action Block `
            -RemoteAddress Internet `
            -Enabled True `
            -Description "LAN Guard: block external inbound to $($r.Desc) port $($r.Port)" `
            | Out-Null
        Write-Host "[已写入] $($r.Name) -- 端口 $($r.Port) ($($r.Desc)) 外网入站已封锁" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "验证结果：" -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName "LAN-Guard-Block-5175","LAN-Guard-Block-18789" -ErrorAction SilentlyContinue `
    | Select-Object DisplayName, Enabled, Action, Direction `
    | Format-Table -AutoSize

Write-Host "完成。按任意键退出..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
