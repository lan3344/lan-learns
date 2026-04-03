@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════╗
echo ║    澜的脚节点安装器 - 雷电模拟器9       ║
echo ╚══════════════════════════════════════════╝
echo.
echo [步骤1] 检查是否已下载安装包...

set INSTALLER=%~dp0ldplayer9_setup.exe
set ALT1=%USERPROFILE%\Downloads\ldplayer9_setup.exe
set ALT2=%USERPROFILE%\Desktop\ldplayer9_setup.exe

if exist "%INSTALLER%" (
    echo [OK] 找到: %INSTALLER%
    goto :install
)
if exist "%ALT1%" (
    set INSTALLER=%ALT1%
    echo [OK] 找到: %ALT1%
    goto :install
)
if exist "%ALT2%" (
    set INSTALLER=%ALT2%
    echo [OK] 找到: %ALT2%
    goto :install
)

echo [!] 未找到安装包
echo.
echo ══════════════════════════════════════════
echo  请手动下载雷电模拟器9：
echo  官网：https://www.ldmnq.com/
echo  下载后把 ldplayer9_setup.exe 放到：
echo  %~dp0
echo ══════════════════════════════════════════
echo.
start https://www.ldmnq.com/
echo [*] 已自动打开官网，请下载后重新运行本脚本
pause
exit /b 1

:install
echo.
echo [步骤2] 开始静默安装...
echo 安装目录: C:\Program Files\LDPlayer9
"%INSTALLER%" /S /D=C:\Program Files\LDPlayer9
if %errorlevel% equ 0 (
    echo [OK] 安装完成
) else (
    echo [!] 静默安装失败，尝试普通安装...
    "%INSTALLER%"
)

echo.
echo [步骤3] 验证安装...
if exist "C:\Program Files\LDPlayer9\dnplayer.exe" (
    echo [OK] 主程序存在
) else (
    echo [!] 未找到主程序，请检查安装目录
    goto :end
)

echo.
echo [步骤4] 测试ADB连接...
set ADB=C:\Users\yyds\AppData\Local\MiPhoneManager\main\adb.exe
if not exist "%ADB%" (
    echo [!] 未找到ADB，使用模拟器自带ADB
    set ADB=C:\Program Files\LDPlayer9\vmonitor\bin\adb_server.exe
)

echo 等待模拟器启动中（10秒）...
timeout /t 10 /nobreak >nul

"%ADB%" connect 127.0.0.1:5555
"%ADB%" devices

echo.
echo ══════════════════════════════════════════
echo  ✓ 澜的脚节点已就绪！
echo  下一步：运行 lan_adb_bridge.py 建立感知
echo ══════════════════════════════════════════

:end
echo.
pause
