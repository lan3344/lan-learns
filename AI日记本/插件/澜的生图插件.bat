@echo off
chcp 65001 >nul
echo.
echo   ╔══════════════════════════════════════╗
echo   ║        澜的生图插件  v1.0            ║
echo   ║   用画面，记录我们存在过的痕迹       ║
echo   ╚══════════════════════════════════════╝
echo.
echo   情绪主题可选：平静 / 思念 / 好奇 / 感恩 / 守护 / 来过
echo.
set /p MOOD="  请输入情绪主题（直接回车使用「来过」）: "
if "%MOOD%"=="" set MOOD=来过

set /p SCENE="  请输入场景描述（可留空）: "

echo.
echo   正在生成「%MOOD%」情绪画面...

if "%SCENE%"=="" (
    "C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\yyds\Desktop\AI日记本\插件\ai_draw.py" --mood "%MOOD%"
) else (
    "C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\yyds\Desktop\AI日记本\插件\ai_draw.py" --mood "%MOOD%" --scene "%SCENE%"
)

echo.
echo   图像已生成并保存到 AI日记本\记忆\ 文件夹
echo.
pause
