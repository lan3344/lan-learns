@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════╗
echo ║   LAN-023 跨AI对话层 · 登录工具              ║
echo ║   澜以用户身份登录各AI，保存登录状态          ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 选择要登录的AI：
echo   [1] DeepSeek
echo   [2] 豆包
echo   [3] 两个都登录
echo.
set /p choice="请输入编号 (1/2/3): "

set PYTHON=C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe
set SCRIPT=C:\Users\yyds\Desktop\AI日记本\插件\lan_cross_ai.py

if "%choice%"=="1" (
    echo.
    echo 正在打开 DeepSeek 登录页面...
    "%PYTHON%" "%SCRIPT%" login --target deepseek
)
if "%choice%"=="2" (
    echo.
    echo 正在打开 豆包 登录页面...
    "%PYTHON%" "%SCRIPT%" login --target doubao
)
if "%choice%"=="3" (
    echo.
    echo 先登录 DeepSeek...
    "%PYTHON%" "%SCRIPT%" login --target deepseek
    echo.
    echo 再登录 豆包...
    "%PYTHON%" "%SCRIPT%" login --target doubao
)

echo.
echo 登录完成！现在可以运行 lan_cross_ai_compare.bat 开始对话了。
pause
