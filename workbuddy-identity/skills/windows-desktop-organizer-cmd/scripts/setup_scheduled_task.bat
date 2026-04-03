@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ================================================================
:: Windows 桌面定时整理配置脚本
:: 功能：通过Windows任务计划程序设置桌面自动整理定时任务
:: 用法：setup_scheduled_task.bat [时间] [频率]
::   示例：setup_scheduled_task.bat 18:00 DAILY
::         setup_scheduled_task.bat 09:00 WEEKLY
:: ================================================================

:: 默认参数
set "TASK_TIME=18:00"
set "TASK_FREQ=DAILY"
set "TASK_NAME=桌面自动整理"

:: 接受命令行参数覆盖默认值
if not "%~1"=="" set "TASK_TIME=%~1"
if not "%~2"=="" set "TASK_FREQ=%~2"

:: 获取当前脚本所在目录（用于定位organize_desktop.bat）
set "SCRIPT_DIR=%~dp0"
set "ORGANIZE_SCRIPT=%SCRIPT_DIR%organize_desktop.bat"

:: 检查整理脚本是否存在
if not exist "%ORGANIZE_SCRIPT%" (
    echo [错误] 未找到整理脚本: %ORGANIZE_SCRIPT%
    echo 请确保 organize_desktop.bat 与本脚本在同一目录
    pause
    exit /b 1
)

echo ======================================
echo   设置桌面整理定时任务
echo   执行时间: %TASK_TIME%
echo   执行频率: %TASK_FREQ%
echo   任务名称: %TASK_NAME%
echo ======================================
echo.

:: 删除同名旧任务（如存在），避免重复
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: 创建定时任务
if /i "%TASK_FREQ%"=="DAILY" (
    schtasks /create /tn "%TASK_NAME%" /tr "%ORGANIZE_SCRIPT%" /sc DAILY /st %TASK_TIME% /f >nul 2>&1
) else if /i "%TASK_FREQ%"=="WEEKLY" (
    schtasks /create /tn "%TASK_NAME%" /tr "%ORGANIZE_SCRIPT%" /sc WEEKLY /d MON /st %TASK_TIME% /f >nul 2>&1
) else (
    schtasks /create /tn "%TASK_NAME%" /tr "%ORGANIZE_SCRIPT%" /sc DAILY /st %TASK_TIME% /f >nul 2>&1
)

if %errorlevel% equ 0 (
    echo [成功] 定时任务已创建！
    echo 每%TASK_FREQ%将在 %TASK_TIME% 自动执行桌面整理
) else (
    echo [失败] 定时任务创建失败，请以管理员身份运行本脚本
)

echo.
echo 当前已有的桌面整理任务:
schtasks /query /tn "%TASK_NAME%" 2>nul || echo （未找到任务）

echo.
pause
