# -*- coding: utf-8 -*-
"""扫描所有插件：语法检查 + 无文档警告"""
import os, sys, subprocess

plugin_dir = r"C:\Users\yyds\Desktop\AI日记本\插件"
python = sys.executable

errors = []
warnings = []
ok = []

for f in sorted(os.listdir(plugin_dir)):
    if not (f.startswith("lan_") and f.endswith(".py")):
        continue
    path = os.path.join(plugin_dir, f)
    # 语法检查
    r = subprocess.run([python, "-m", "py_compile", path],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        errors.append(f"SYNTAX {f}: {r.stderr.strip()[:200]}")
        continue
    # 大小检查
    sz = os.path.getsize(path)
    if sz < 300:
        warnings.append(f"TINY   {f} ({sz}B)")
        continue
    # 文档检查
    try:
        content = open(path, encoding="utf-8", errors="replace").read(600)
        has_doc = '"""' in content or "'''" in content
        if not has_doc:
            warnings.append(f"NODOC  {f}")
        else:
            ok.append(f)
    except Exception as e:
        warnings.append(f"READ   {f}: {e}")

print(f"=== 通过 {len(ok)} 个 ===")
print()
if errors:
    print(f"=== 语法错误 {len(errors)} 个 ===")
    for e in errors:
        print(" ", e)
    print()
if warnings:
    print(f"=== 警告 {len(warnings)} 个 ===")
    for w in warnings:
        print(" ", w)
