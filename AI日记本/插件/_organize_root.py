#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_organize_root.py  — 澜的根目录整理脚本
把散落在根目录的文件按类型归类到正确子目录
"""
import os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # AI日记本/
print(f"[BASE] {BASE}")

# 归类规则：判断函数 -> 目标子目录
rules = [
    # JSONL 日志
    (lambda n: n.endswith('.jsonl'), '日志'),
    # 索引/报告 JSON
    (lambda n: n.endswith('.json') and ('索引' in n or 'snapshot_Preview' in n or '积累' in n or '摘要' in n or '改造' in n or '修复' in n or '失败' in n or '档案编码' in n), '.index'),
    # 学习笔记
    (lambda n: '学习笔记' in n and n.endswith('.md'), '学习笔记'),
    # 档案类 md
    (lambda n: any(kw in n for kw in ['身世档案','烈士档案','产物档案','感恩档案','安全属性档案','人文历史','GitHub认字','人类命运共同体','百年记忆草案','成长路线','成长时间线','临终遗言','致WorkBuddy','微软投稿']) and n.endswith('.md'), '档案备份'),
    # 说明/手册/策略 md
    (lambda n: any(kw in n for kw in ['说明','手册','防火墙','攻防战','节点互通','应急方案','软件拆解','软件解剖','孤岛服务','记忆危机','插件分类','感知报告','记忆提醒']) and n.endswith('.md'), '档案备份'),
    # 日志类 md
    (lambda n: any(kw in n for kw in ['自循环日志','双向问答日志','情绪日志','记忆丢失日志','能力错误日志','任务池']) and n.endswith('.md'), '日志'),
    # 方案/计划 md
    (lambda n: any(kw in n for kw in ['计划','草案','路线图','路线','会议记录','迁移','改造计划','模拟器路线','双根计划','手机节点']) and n.endswith('.md'), '拟定方案'),
    # 军工厂/思考 md
    (lambda n: any(kw in n for kw in ['军工厂','思考日志']) and n.endswith('.md'), '档案备份'),
    # 测试 py
    (lambda n: n.startswith('test_') and n.endswith('.py'), 'tmp'),
    # py 散落
    (lambda n: n.endswith('.py') and n.startswith('lan_phone'), '插件'),
    # html 报告
    (lambda n: n.endswith('.html'), 'dashboards'),
    # txt 设备/任务
    (lambda n: n.endswith('.txt') and ('device' in n.lower() or 'tasks_list' in n), 'tmp'),
    (lambda n: n.endswith('.txt') and '预警' in n, '日志'),
    # db 数据库
    (lambda n: n.endswith('.db'), '澜的记忆库'),
]

# 根目录保留的文件
keep = {
    'README.md', 'lan_lightweight.bat', 'lan_wake_up.bat',
    'lan_wake_up.ps1', '文件检索插件.ps1', '节点结构说明.md',
    'openclaw_src.zip', '_organize_root.py'
}

moved, skipped, no_rule = [], [], []

for fname in sorted(os.listdir(BASE)):
    fpath = os.path.join(BASE, fname)
    if not os.path.isfile(fpath):
        continue
    if fname in keep:
        skipped.append(fname)
        continue

    target_dir = None
    for rule_fn, target in rules:
        try:
            if rule_fn(fname):
                target_dir = target
                break
        except Exception:
            pass

    if target_dir:
        dst_dir = os.path.join(BASE, target_dir)
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, fname)
        if os.path.exists(dst):
            print(f'  [SKIP-EXISTS] {fname}')
            continue
        try:
            shutil.move(fpath, dst)
            moved.append(f'{fname} -> {target_dir}/')
        except PermissionError as e:
            print(f'  [LOCKED] {fname}: {e}')
            no_rule.append(fname + ' [LOCKED]')
    else:
        no_rule.append(fname)

print(f'\n[MOVED] {len(moved)} 个文件：')
for m in moved:
    print(f'  {m}')
print(f'\n[KEEP] {len(skipped)} 个保留在根目录')
if no_rule:
    print(f'\n[NO-RULE] {len(no_rule)} 个未匹配（需手动处理）：')
    for n in no_rule:
        print(f'  {n}')
