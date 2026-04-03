@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ================================================================
:: Windows 桌面自动整理脚本 (CMD版)
:: 功能：按文件类型自动分类整理桌面文件
:: 依赖：仅Windows原生CMD命令，无需额外软件
:: 作者：WorkBuddy Desktop Organizer Skill
:: ================================================================

:: 自动获取当前用户桌面路径（兼容所有Windows版本及用户名）
set "DESKTOP_PATH=%USERPROFILE%\Desktop"

:: 定义分类文件夹名称（可根据需求修改）
set "DOCS_FOLDER=%DESKTOP_PATH%\文档文件"
set "PICS_FOLDER=%DESKTOP_PATH%\图片文件"
set "VIDEOS_FOLDER=%DESKTOP_PATH%\视频文件"
set "AUDIO_FOLDER=%DESKTOP_PATH%\音频文件"
set "ARCHIVES_FOLDER=%DESKTOP_PATH%\压缩包文件"
set "CODE_FOLDER=%DESKTOP_PATH%\代码文件"
set "OTHERS_FOLDER=%DESKTOP_PATH%\其他文件"

echo ======================================
echo   Windows 桌面整理工具 - CMD版
echo   桌面路径: %DESKTOP_PATH%
echo ======================================
echo.

:: 自动创建分类文件夹（不存在则新建，静默不报错）
if not exist "%DOCS_FOLDER%"     mkdir "%DOCS_FOLDER%"
if not exist "%PICS_FOLDER%"     mkdir "%PICS_FOLDER%"
if not exist "%VIDEOS_FOLDER%"   mkdir "%VIDEOS_FOLDER%"
if not exist "%AUDIO_FOLDER%"    mkdir "%AUDIO_FOLDER%"
if not exist "%ARCHIVES_FOLDER%" mkdir "%ARCHIVES_FOLDER%"
if not exist "%CODE_FOLDER%"     mkdir "%CODE_FOLDER%"
if not exist "%OTHERS_FOLDER%"   mkdir "%OTHERS_FOLDER%"

echo [1/6] 整理文档文件...
:: 文档类文件移动（覆盖全格式办公文件）
move /y "%DESKTOP_PATH%\*.doc"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.docx" "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.pdf"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.txt"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.ppt"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.pptx" "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.xls"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.xlsx" "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.csv"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.md"   "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.odt"  "%DOCS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.wps"  "%DOCS_FOLDER%" >nul 2>&1
echo    完成

echo [2/6] 整理图片文件...
:: 图片类文件移动（覆盖主流图片格式）
move /y "%DESKTOP_PATH%\*.jpg"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.jpeg" "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.png"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.gif"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.bmp"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.webp" "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.svg"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.ico"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.tiff" "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.tif"  "%PICS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.heic" "%PICS_FOLDER%" >nul 2>&1
echo    完成

echo [3/6] 整理视频文件...
:: 视频类文件移动（覆盖主流视频格式）
move /y "%DESKTOP_PATH%\*.mp4"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.avi"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.mkv"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.mov"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.flv"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.wmv"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.m4v"  "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.ts"   "%VIDEOS_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.webm" "%VIDEOS_FOLDER%" >nul 2>&1
echo    完成

echo [4/6] 整理音频文件...
:: 音频类文件移动（覆盖主流音频格式）
move /y "%DESKTOP_PATH%\*.mp3"  "%AUDIO_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.wav"  "%AUDIO_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.flac" "%AUDIO_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.aac"  "%AUDIO_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.ogg"  "%AUDIO_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.wma"  "%AUDIO_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.m4a"  "%AUDIO_FOLDER%" >nul 2>&1
echo    完成

echo [5/6] 整理压缩包文件...
:: 压缩包类文件移动（覆盖主流压缩格式）
move /y "%DESKTOP_PATH%\*.zip"  "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.rar"  "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.7z"   "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.tar"  "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.gz"   "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.bz2"  "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.xz"   "%ARCHIVES_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.iso"  "%ARCHIVES_FOLDER%" >nul 2>&1
echo    完成

echo [6/6] 整理代码与其他文件...
:: 代码类文件移动
move /y "%DESKTOP_PATH%\*.py"   "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.js"   "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.html" "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.css"  "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.java" "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.cpp"  "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.c"    "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.sh"   "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.json" "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.xml"  "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.yaml" "%CODE_FOLDER%" >nul 2>&1
move /y "%DESKTOP_PATH%\*.yml"  "%CODE_FOLDER%" >nul 2>&1

:: 剩余文件归类到"其他文件"（排除快捷方式.lnk、文件夹，避免误移软件快捷方式）
for %%i in ("%DESKTOP_PATH%\*.*") do (
    if /i not "%%~xi"==".lnk" (
        if /i not "%%~xi"==".bat" (
            move /y "%%i" "%OTHERS_FOLDER%" >nul 2>&1
        )
    )
)
echo    完成

echo.
echo ======================================
echo   整理完成！桌面文件已按类型分类：
echo   - 文档文件 ^(doc/pdf/txt/ppt/xls等^)
echo   - 图片文件 ^(jpg/png/gif/bmp等^)
echo   - 视频文件 ^(mp4/avi/mkv/mov等^)
echo   - 音频文件 ^(mp3/wav/flac等^)
echo   - 压缩包文件 ^(zip/rar/7z等^)
echo   - 代码文件 ^(py/js/html/css等^)
echo   - 其他文件 ^(以上未涵盖的类型^)
echo ======================================
pause
