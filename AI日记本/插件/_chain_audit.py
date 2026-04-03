# -*- coding: utf-8 -*-
"""临时审计脚本：检测能力连接断链"""
import json, os

manifest_path = r'C:\Users\yyds\Desktop\AI日记本\插件\capability_manifest.json'
plugin_dir    = r'C:\Users\yyds\Desktop\AI日记本\插件'

with open(manifest_path, encoding='utf-8') as f:
    manifest = json.load(f)

caps = manifest['capabilities']
cap_plugins = {c['plugin'] for c in caps}

print("=== 一、depends 断链检测 ===")
broken = []
for c in caps:
    for dep in c.get('depends', []):
        dep_path = os.path.join(plugin_dir, dep)
        registered = dep in cap_plugins
        exists = os.path.exists(dep_path)
        if not registered or not exists:
            broken.append((c['id'], dep, registered, exists))
            print(f"  BROKEN  [{c['id']}] -> [{dep}]  注册:{registered}  文件:{exists}")
if not broken:
    print("  OK  所有 depends 依赖均存在且已注册")

print()
print("=== 二、孤立能力（无任何连接）===")
depended_by = {}
for c in caps:
    for dep in c.get('depends', []):
        depended_by.setdefault(dep, []).append(c['id'])

isolated = []
for c in caps:
    plugin = c['plugin']
    has_deps  = bool(c.get('depends'))
    is_depended = plugin in depended_by
    if not has_deps and not is_depended:
        isolated.append(c['id'])

print(f"  孤立能力：{len(isolated)} 个")
for i in isolated:
    print(f"    · {i}")

print()
print("=== 三、连接图（被依赖次数）===")
for c in caps:
    times = len(depended_by.get(c['plugin'], []))
    bar = '*' * times if times else '.'
    print(f"  {bar:5s}  {c['id']:22s}  {c['name']}")

print()
print("=== 四、当前 self_loop 的依赖链 ===")
# 找 self_loop 的直接依赖，再找依赖的依赖
def get_deps(cap_id, caps_list):
    for c in caps_list:
        if c['id'] == cap_id:
            return c.get('depends', [])
    return []

def trace(cap_id, caps_list, depth=0, visited=None):
    if visited is None:
        visited = set()
    if cap_id in visited:
        return
    visited.add(cap_id)
    deps = get_deps(cap_id, caps_list)
    for d in deps:
        # find cap by plugin name
        for c in caps_list:
            if c['plugin'] == d:
                print("  " + "  " * depth + f"-> {c['id']} ({c['name']})")
                trace(c['id'], caps_list, depth+1, visited)

print("  self_loop 的依赖树：")
trace('self_loop', caps)
