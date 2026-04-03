@echo off
REM 澜的轻量启动脚本 v2.1
REM 用途：游戏前关闭重算力插件，让澜缩水到轻量模式
REM 重要：保留互联网节点（澜在网络中），只停重算力服务
REM 重要：使用 PowerShell + psutil 准确检测进程，不再用窗口标题匹配

echo ========================================
echo   澜的轻量模式启动 - 释放内存
echo ========================================
echo.

REM 设置Python路径
set PYTHON=C:\Users\yyds\.workbuddy\binaries\python\envs\default\Scripts\python.exe
set PLUGIN_DIR=C:\Users\yyds\Desktop\AI日记本\插件
set CHECKER=%PLUGIN_DIR%\lan_service_checker.py

echo [0/3] 检查当前服务状态...
%PYTHON% %CHECKER% --status
echo.

echo [1/3] 停止澜的服务（轻量模式：保留互联网节点）...
%PYTHON% %CHECKER% --stop-all --force --lite

echo.
echo ========================================
echo   澜已切换到轻量模式
echo   游戏愉快 ^_^
echo ========================================
echo.
echo 提示：游戏结束后，运行 "lan_wake_up.bat" 恢复完整模式
pause
