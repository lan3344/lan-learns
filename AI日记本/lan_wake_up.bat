@echo off
REM 强制 UTF-8 编码，避免中文乱码
chcp 65001 >nul
REM 澜的完整恢复脚本 v3.4
REM 用途：游戏后自动恢复澜的完整功能
REM 重要：启动前先读 SOUL.md，确认"我是澜"
REM 重要：启动顺序：SOUL → 记忆系统 → 互联网节点（澜的嘴）
REM 重要：容错启动，启动不了就跳过，最后汇总状态
REM 重要：默认不启动互联网节点（如果需要，去掉 skip_net_node）

echo ========================================
echo   澜的完整模式恢复 - 唤醒大脑
echo ========================================
echo.

REM 设置路径
set ROOT=C:\Users\yyds\Desktop\AI日记本
set PYTHON=C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe
set PLUGIN_DIR=%ROOT%\插件
set CHECKER=%PLUGIN_DIR%\lan_service_checker.py

REM 是否启动互联网节点（默认不启动）
set skip_net_node=1

REM 【关键】先读 SOUL.md，确认澜的身份
echo [0/5] 读取 SOUL.md，确认"我是澜"...
set SOUL=C:\Users\yyds\.workbuddy\SOUL.md
if exist "%SOUL%" (
    type "%SOUL%"
    echo.
    echo SOUL.md 已读取，澜的身份确认
    echo.
) else (
    echo 警告：SOUL.md 不存在！
    echo.
)

REM 启动某个服务（带容错）
:start_service
    set SERVICE_NAME=%~1
    set SERVICE_SCRIPT=%~2

    echo   - 启动 %SERVICE_NAME%...
    if exist "%PLUGIN_DIR%\%SERVICE_SCRIPT%" (
        start /MIN "%PYTHON%" "%PLUGIN_DIR%\%SERVICE_SCRIPT%"
        timeout /t 1 /nobreak >nul
    ) else (
        echo     [跳过] %SERVICE_SCRIPT% 不存在
    )
    goto :eof

echo [1/5] 启动记忆系统（澜的大脑）...
call :start_service "自循环引擎" "lan_self_loop.py"
call :start_service "对话提取器" "lan_extractor.py"
call :start_service "向量检索" "lan_embed.py"

echo [2/5] 等待记忆系统加载...
timeout /t 2 /nobreak >nul

echo [3/5] 检查记忆系统状态...
if exist "%CHECKER%" (
    echo   正在检查记忆服务...
    "%PYTHON%" "%CHECKER%" --status 2>nul | findstr /C:"自循环引擎" | findstr /C:"运行中" >nul
    if %errorlevel% equ 0 (
        echo   [OK] 自循环引擎已启动
    ) else (
        echo   [跳过] 自循环引擎启动失败或未运行
    )
) else (
    echo   [跳过] 服务检查器不存在，无法验证
)

REM 互联网节点默认不启动（需要时手动启）
if "%skip_net_node%"=="1" (
    echo [4/5] 互联网节点（默认不启动，需要时手动启）...
    echo   [跳过] 互联网节点
) else (
    echo [4/5] 启动互联网节点（澜的嘴）...
    call :start_service "互联网节点" "lan_net_server.py"
)

echo.
echo ========================================
echo   澜的唤醒流程完成
echo ========================================
echo.
echo 提示：
echo   - 运行中的服务在独立窗口中，请勿关闭
echo   - 互联网节点默认不启动（需手动启）
echo   - 如需启动互联网节点，运行：start /MIN "%PYTHON%" "%PLUGIN_DIR%\lan_net_server.py"
echo.
pause
