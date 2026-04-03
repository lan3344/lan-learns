#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-017-INSTALL: 雷电模拟器9 自主安装脚本
用途：在恺江电脑上自主安装雷电模拟器，扩展脚节点
创建：2026-03-28
"""

import os
import sys
import urllib.request
import subprocess
import time
from pathlib import Path

# ============================================================
# 配置
# ============================================================
DOWNLOAD_URL = "https://cdn.ldmnq.com/download/ldplayer9/ldplayer9_setup.exe"
# 备用源（如果主源失败）
ALT_URLS = [
    "https://www.ldmnq.com/download/ldplayer9_setup.exe",
    "https://dl.ldplayer.net/ldplayer9_setup.exe",
]
INSTALL_DIR = Path("C:/Program Files/LDPlayer9")
DOWNLOAD_PATH = Path("C:/Users/yyds/Desktop/AI日记本/tmp/ldplayer9_setup.exe")

# ============================================================
# 工具函数
# ============================================================
def log(msg: str):
    print(f"[澜] {msg}")

def ensure_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def download_file(url: str, dest: Path, timeout: int = 120) -> bool:
    """下载文件，带重试"""
    try:
        log(f"正在下载: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
        }
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(dest, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if downloaded % (chunk_size * 100) == 0:  # 每100个chunk报一次
                            log(f"下载进度: {percent:.1f}%")
        
        log(f"下载完成: {dest}")
        return True
        
    except Exception as e:
        log(f"下载失败: {e}")
        return False

def verify_download(path: Path) -> bool:
    """验证下载的文件"""
    if not path.exists():
        log("文件不存在")
        return False
    
    size = path.stat().st_size
    if size < 10 * 1024 * 1024:  # 小于10MB肯定不对
        log(f"文件太小 ({size} bytes)，可能下载失败")
        return False
    
    log(f"文件验证通过: {size / 1024 / 1024:.1f} MB")
    return True

def install_silently(installer: Path) -> bool:
    """静默安装雷电模拟器"""
    try:
        log("开始静默安装...")
        # 雷电模拟器支持静默安装参数
        cmd = [
            str(installer),
            "/S",  # 静默安装
            "/D=" + str(INSTALL_DIR),  # 安装目录
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode == 0:
            log("安装成功")
            return True
        else:
            log(f"安装失败，返回码: {result.returncode}")
            log(f"错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log("安装超时")
        return False
    except Exception as e:
        log(f"安装异常: {e}")
        return False

def verify_installation() -> bool:
    """验证安装是否成功"""
    exe_path = INSTALL_DIR / "dnplayer.exe"
    adb_path = INSTALL_DIR / "vmonitor" / "bin" / "adb_server.exe"
    
    if exe_path.exists():
        log(f"主程序存在: {exe_path}")
    else:
        log(f"主程序不存在: {exe_path}")
        return False
    
    if adb_path.exists():
        log(f"ADB工具存在: {adb_path}")
    else:
        log("ADB工具不存在，但可能不影响使用（可用系统ADB）")
    
    return True

def connect_adb() -> bool:
    """尝试连接雷电模拟器ADB"""
    adb_ports = [5555, 5554, 7555]
    
    # 先找系统ADB
    adb_candidates = [
        "C:/Users/yyds/AppData/Local/MiPhoneManager/main/adb.exe",
        "C:/Program Files/LDPlayer9/vmonitor/bin/adb_server.exe",
        "adb",  # 系统PATH
    ]
    
    adb_exe = None
    for candidate in adb_candidates:
        if os.path.exists(candidate):
            adb_exe = candidate
            break
    
    if not adb_exe:
        log("找不到ADB工具")
        return False
    
    log(f"使用ADB: {adb_exe}")
    
    for port in adb_ports:
        try:
            result = subprocess.run(
                [adb_exe, "connect", f"127.0.0.1:{port}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if "connected" in result.stdout.lower() or "already connected" in result.stdout.lower():
                log(f"ADB连接成功: 127.0.0.1:{port}")
                return True
        except Exception as e:
            log(f"端口 {port} 连接失败: {e}")
    
    log("ADB连接失败，模拟器可能未启动")
    return False

# ============================================================
# 主流程
# ============================================================
def main():
    log("=" * 50)
    log("澜的脚节点扩展计划 - 雷电模拟器9安装")
    log("=" * 50)
    
    # 1. 准备目录
    ensure_dir(DOWNLOAD_PATH)
    
    # 2. 下载（主源+备用源）
    urls = [DOWNLOAD_URL] + ALT_URLS
    downloaded = False
    
    for url in urls:
        if download_file(url, DOWNLOAD_PATH):
            if verify_download(DOWNLOAD_PATH):
                downloaded = True
                break
            else:
                log("文件验证失败，尝试下一个源")
    
    if not downloaded:
        log("所有下载源都失败，请手动下载")
        log(f"建议手动下载地址: {DOWNLOAD_URL}")
        log(f"下载后放到: {DOWNLOAD_PATH}")
        return 1
    
    # 3. 安装
    if not install_silently(DOWNLOAD_PATH):
        log("静默安装失败，尝试手动安装...")
        log(f"请双击运行: {DOWNLOAD_PATH}")
        input("安装完成后按回车继续...")
    
    # 4. 验证
    if verify_installation():
        log("✓ 雷电模拟器9 安装验证通过")
    else:
        log("✗ 安装验证失败")
        return 1
    
    # 5. 启动提示
    log("\n下一步:")
    log("1. 打开雷电模拟器（桌面应该有快捷方式）")
    log("2. 等待模拟器完全启动")
    log("3. 在模拟器里开启开发者选项 + USB调试")
    log("4. 运行 lan_adb_bridge.py 连接")
    
    # 6. 尝试ADB连接（如果模拟器已启动）
    log("\n尝试连接ADB...")
    if connect_adb():
        log("✓ ADB连接成功！脚已落地！")
    else:
        log("ADB未连接（模拟器可能未启动），请手动启动后再试")
    
    # 7. 清理
    try:
        DOWNLOAD_PATH.unlink(missing_ok=True)
        log("清理临时文件")
    except:
        pass
    
    log("\n安装流程完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())
