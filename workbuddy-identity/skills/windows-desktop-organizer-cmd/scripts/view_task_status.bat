@echo off
chcp 65001 >nul 2>&1

:: ================================================================
:: 查看/删除桌面整理定时任务状态脚本
:: ================================================================

set "TASK_NAME=桌面自动整理"

echo ======================================
echo   桌面整理定时任务状态查询
echo ======================================
echo.

schtasks /query /tn "%TASK_NAME%" /fo LIST 2>nul
if errorlevel 1 (
    echo [提示] 当前未设置桌面整理定时任务
    echo 请运行 setup_scheduled_task.bat 创建定时任务
)

echo.
set /p "DEL_CHOICE=是否删除现有定时任务？(y/N): "
if /i "%DEL_CHOICE%"=="y" (
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
    if %errorlevel% equ 0 (
        echo [成功] 定时任务已删除
    ) else (
        echo [提示] 无可删除的定时任务，或需要管理员权限
    )
)

echo.
pause
