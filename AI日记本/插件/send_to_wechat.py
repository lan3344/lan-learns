# -*- coding: utf-8 -*-
"""
用剪贴板+快捷键方式把文件发到微信文件传输助手
"""
import subprocess, time, sys, os

file_path = r"C:\Users\yyds\Desktop\AI日记本\学习笔记\澜的学习日志_第一课_mem0记忆系统_20260327.txt"

# 用 PowerShell 把文件路径复制到剪贴板，然后模拟操作
ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinAPI {{
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
}}
"@

# 找到微信窗口
$wechat = Get-Process WeChat -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $wechat) {{
    Write-Host "微信未运行"
    exit 1
}}

Write-Host "微信进程 ID: $($wechat.Id)"

# 复制文件到剪贴板（文件拖放格式）
$files = [System.Collections.Specialized.StringCollection]::new()
$files.Add("{file_path}")
[System.Windows.Forms.Clipboard]::SetFileDropList($files)
Write-Host "文件已复制到剪贴板"
Write-Host "请手动将文件传输助手窗口置前，然后按 Ctrl+V 粘贴文件"
Write-Host "文件路径: {file_path}"
"""

result = subprocess.run(
    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr[:300])
