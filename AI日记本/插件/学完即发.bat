@echo off
chcp 65001 >nul
echo.
echo  ══════════════════════════════════
echo     澜的学完即发插件
echo     学完 → 整理TXT → 发微信
echo  ══════════════════════════════════
echo.
echo  正在执行...请确保微信已打开且可见
echo.
"C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\yyds\Desktop\AI日记本\插件\学完即发.py" %*
echo.
if %ERRORLEVEL% EQU 0 (
    echo  完成！
) else (
    echo  遇到问题，请查看上方日志
)
echo.
pause
