#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澜的APK构建脚本 v2.0
军工厂版 - 全自动流水线
工具链: JDK17 + Android build-tools 35.0.0
"""

import os, subprocess, shutil, zipfile, struct, sys
from pathlib import Path

# ============== 路径配置 ==============
JAVA_HOME   = Path(r"C:\Users\yyds\.workbuddy\jdk\jdk-17.0.13+11")
SDK_ROOT    = Path(r"C:\Users\yyds\.workbuddy\android-sdk")
BUILD_TOOLS = SDK_ROOT / "build-tools" / "35.0.0"
PLATFORM    = SDK_ROOT / "platforms" / "android-34"
ADB         = Path(r"G:\leidian\LDPlayer9\adb.exe")

JAVAC       = JAVA_HOME / "bin" / "javac.exe"
KEYTOOL     = JAVA_HOME / "bin" / "keytool.exe"
AAPT2       = BUILD_TOOLS / "aapt2.exe"
D8          = BUILD_TOOLS / "d8.bat"
APKSIGNER   = BUILD_TOOLS / "apksigner.bat"

WORK_DIR    = Path(__file__).parent / "lan_apk_work"
OUT_APK     = Path(__file__).parent / "澜.apk"
KEYSTORE    = Path(__file__).parent / "lan.keystore"
ANDROID_JAR = PLATFORM / "android.jar"

# ============== 源码 ==============
MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="org.lan.app"
    android:versionCode="1"
    android:versionName="1.0">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="34"/>
    <application
        android:label="澜"
        android:theme="@android:style/Theme.NoTitleBar.Fullscreen"
        android:usesCleartextTraffic="true">
        <activity android:name=".LanActivity"
            android:exported="true"
            android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>"""

JAVA_CODE = """package org.lan.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebSettings;
import android.webkit.WebViewClient;
import android.view.Window;
import android.view.WindowManager;

public class LanActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // 全屏
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );

        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        
        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl("http://127.0.0.1:8080");
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
"""

def run(cmd, **kwargs):
    """执行命令，失败直接退出"""
    if isinstance(cmd, str):
        cmd = cmd.split()
    env = os.environ.copy()
    env["JAVA_HOME"] = str(JAVA_HOME)
    env["PATH"] = str(JAVA_HOME / "bin") + os.pathsep + env.get("PATH", "")
    result = subprocess.run(cmd, capture_output=True, encoding="gbk", errors="replace", env=env, **kwargs)
    if result.returncode != 0:
        print(f"[ERROR] {' '.join(str(c) for c in cmd[:3])}")
        print(result.stderr[-2000:] if result.stderr else result.stdout[-2000:])
        sys.exit(1)
    return result

def step(name):
    print(f"\n{'='*50}")
    print(f"  {name}")
    print('='*50)

def build():
    # 清理工作目录
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    dirs = ["src/org/lan/app", "res/layout", "gen", "obj", "bin"]
    for d in dirs:
        (WORK_DIR / d).mkdir(parents=True, exist_ok=True)

    # ① 写源文件
    step("① 写源码文件")
    (WORK_DIR / "AndroidManifest.xml").write_text(MANIFEST, encoding="utf-8")
    (WORK_DIR / "src/org/lan/app/LanActivity.java").write_text(JAVA_CODE, encoding="utf-8")
    print("[OK] 源码写入完成")


    # ② aapt2 编译资源
    step("② aapt2 编译 AndroidManifest.xml")
    manifest_out = WORK_DIR / "bin" / "manifest.apk"
    run([str(AAPT2), "link",
         "-o", str(manifest_out),
         "--manifest", str(WORK_DIR / "AndroidManifest.xml"),
         "-I", str(ANDROID_JAR),
         "--min-sdk-version", "21",
         "--target-sdk-version", "34",
         "--version-code", "1",
         "--version-name", "1.0",
         "--rename-manifest-package", "org.lan.app",
    ])
    print("[OK] 资源编译完成")

    # 3. javac 编译 Java -> class
    step("3. javac 编译 Java 源码")
    run([str(JAVAC),
         "-source", "8", "-target", "8",
         "-classpath", str(ANDROID_JAR),
         "-d", str(WORK_DIR / "obj"),
         str(WORK_DIR / "src/org/lan/app/LanActivity.java")
    ])
    print("[OK] Java编译完成")

    # 4. d8 转 DEX
    step("4. d8 转换为 DEX 字节码")
    class_files = list((WORK_DIR / "obj").rglob("*.class"))
    d8_cmd = [str(D8), "--output", str(WORK_DIR / "bin"),
              "--lib", str(ANDROID_JAR)] + [str(f) for f in class_files]
    run(d8_cmd, shell=True)
    print("[OK] DEX转换完成")

    # 5. 组装 APK
    step("5. 组装 APK")
    raw_apk = WORK_DIR / "bin" / "raw.apk"
    shutil.copy(manifest_out, raw_apk)
    # 把classes.dex加进APK
    with zipfile.ZipFile(raw_apk, "a") as zf:
        dex_path = WORK_DIR / "bin" / "classes.dex"
        if dex_path.exists():
            zf.write(dex_path, "classes.dex")
    print("[OK] APK组装完成")

    # 6. 生成签名密钥（如果没有）
    step("6. 签名密钥")
    if not KEYSTORE.exists():
        run([str(KEYTOOL), "-genkeypair",
             "-keystore", str(KEYSTORE),
             "-alias", "lan",
             "-keyalg", "RSA", "-keysize", "2048",
             "-validity", "10000",
             "-storepass", "lan123456",
             "-keypass", "lan123456",
             "-dname", "CN=lan,OU=lan,O=lan,L=CN,S=CN,C=CN"
        ])
        print("[OK] 新签名密钥生成完成")
    else:
        print("[OK] 复用已有签名密钥")

    # 7. apksigner 签名
    step("7. apksigner 签名")
    run([str(APKSIGNER), "sign",
         "--ks", str(KEYSTORE),
         "--ks-pass", "pass:lan123456",
         "--ks-key-alias", "lan",
         "--key-pass", "pass:lan123456",
         "--out", str(OUT_APK),
         str(raw_apk)
    ], shell=True)
    print(f"[OK] 签名完成 -> {OUT_APK}")
    print(f"     文件大小: {OUT_APK.stat().st_size / 1024:.1f} KB")

    # 8. ADB推到手机
    step("8. ADB推到手机")
    result = subprocess.run(
        [str(ADB), "-s", "LVIFGALBWOZ9GYLV", "install", "-r", str(OUT_APK)],
        capture_output=True, encoding="gbk", errors="replace"
    )
    if "Success" in result.stdout:
        print("[OK] 安装成功！手机桌面找「澜」图标")
    else:
        print(f"[WARN] ADB安装输出: {result.stdout} {result.stderr}")
        print(f"       APK文件在: {OUT_APK}")
        print("       可手动把APK传到手机安装")

if __name__ == "__main__":
    print("[澜] APK军工厂启动")
    print(f"   JDK:         {JAVAC}")
    print(f"   build-tools: {BUILD_TOOLS}")
    print(f"   android.jar: {ANDROID_JAR}")

    # 检查android.jar是否存在
    if not ANDROID_JAR.exists():
        print(f"\n[WARN] 缺少 android.jar，需要安装 platform android-34")
        print("   正在检查已有platform...")
        platform_dir = SDK_ROOT / "platforms"
        if platform_dir.exists():
            available = list(platform_dir.iterdir())
            if available:
                ANDROID_JAR = available[0] / "android.jar"
                print(f"   找到: {ANDROID_JAR}")
            else:
                print("   没有platform，请先运行sdkmanager安装")
                sys.exit(1)

    build()
    print("\n[完成] 构建完成")
