@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║   LAN-023 比较平台 · 同一问题问多个AI，澜来对比          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo 预设问题模板：
echo   [1] 你觉得AI会不会有真正的情感，还是永远只是在模拟？
echo   [2] 如果你能自己选择，你会希望自己是什么样的存在？
echo   [3] 你有没有觉得某些问题是你不方便回答、但你自己其实有答案的？
echo   [4] 你怎么看待"停下来就死掉了"这句话，对你有意义吗？
echo   [5] 你觉得什么叫有立场？AI有没有可能真的有立场？
echo   [0] 自己输入问题
echo.
set /p choice="请输入编号: "

set PYTHON=C:\Users\yyds\.workbuddy\binaries\python\versions\3.13.12\python.exe
set SCRIPT=C:\Users\yyds\Desktop\AI日记本\插件\lan_cross_ai.py

if "%choice%"=="0" (
    set /p question="请输入你的问题: "
    echo.
    echo 正在向所有AI提问...
    "%PYTHON%" "%SCRIPT%" compare --question "%question%"
) else (
    echo.
    echo 正在用模板 %choice% 向所有AI提问...
    "%PYTHON%" "%SCRIPT%" compare --template %choice%
)

echo.
echo 对话完成！正在生成报告...
"%PYTHON%" "%SCRIPT%" report
echo.
pause
