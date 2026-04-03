#!/usr/bin/env python3
"""
LAN-052 · 技能收集器
功能：收集、分析、归档来自其他AI系统的技能教训，避免重复造轮子。
设计原则：
  1. 不自循环：与 lan_experience.py、lan_failure_log.py、lan_rebuild_log.py 形成链条
  2. 避免孤岛：技能教训可被其他插件检索引用
  3. 实时更新：支持动态添加、检索、更新

数据格式（每条技能教训）：
{
  "id": "SKILL-001",
  "skill": "记忆压缩",
  "from": "LobsterAI",
  "purpose": "解决上下文长度限制",
  "constraint": "Token数量有限",
  "solution": "提取关键点，丢弃冗余",
  "lesson": "有限资源下必须提炼本质，不能全盘保留",
  "principle": "信息密度 > 信息总量",
  "applicable_scenario": "当面临资源瓶颈时，优先保留核心语义",
  "related_failures": [],      # 关联的失败日志ID
  "related_experiences": [],   # 关联的经验记忆ID
  "related_rebuilds": [],      # 关联的改造日志ID
  "can_reuse": true,
  "reuse_method": "lan_compact.py 已实现蒸馏算法",
  "risk": "过度压缩可能导致关键细节丢失",
  "created_at": "2026-03-30T13:45:00",
  "updated_at": "2026-03-30T13:45:00"
}
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path

# 路径配置
BASE_DIR = Path(__file__).parent
SKILL_DB = BASE_DIR / "skill_collector.db"
SKILL_JSON = BASE_DIR / "skill_lessons.json"

class SkillCollector:
    def __init__(self):
        self.db_path = SKILL_DB
        self.json_path = SKILL_JSON
        self.init_db()
        self.load_default_skills()  # 加载默认技能教训
    
    def init_db(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                skill TEXT NOT NULL,
                source TEXT NOT NULL,
                purpose TEXT,
                constraint_text TEXT,
                solution TEXT,
                lesson TEXT NOT NULL,
                principle TEXT,
                applicable_scenario TEXT,
                related_failures TEXT DEFAULT '[]',
                related_experiences TEXT DEFAULT '[]',
                related_rebuilds TEXT DEFAULT '[]',
                can_reuse BOOLEAN DEFAULT 1,
                reuse_method TEXT,
                risk TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skill_relations (
                skill_id TEXT NOT NULL,
                related_type TEXT NOT NULL,  -- 'failure', 'experience', 'rebuild'
                related_id TEXT NOT NULL,
                FOREIGN KEY (skill_id) REFERENCES skills (id)
            )
        ''')
        conn.commit()
        conn.close()
    
    def load_default_skills(self):
        """加载默认技能教训（龙虾 + 鼻祖）"""
        default_skills = [
            {
                "id": "SKILL-001",
                "skill": "记忆压缩",
                "from": "LobsterAI",
                "purpose": "解决上下文长度限制",
                "constraint": "Token数量有限",
                "solution": "提取关键点，丢弃冗余",
                "lesson": "有限资源下必须提炼本质，不能全盘保留",
                "principle": "信息密度 > 信息总量",
                "applicable_scenario": "当面临资源瓶颈时，优先保留核心语义",
                "can_reuse": True,
                "reuse_method": "lan_compact.py 已实现蒸馏算法",
                "risk": "过度压缩可能导致关键细节丢失"
            },
            {
                "id": "SKILL-002",
                "skill": "多模态理解",
                "from": "LobsterAI",
                "purpose": "适应现实世界复杂输入",
                "constraint": "单一模态不足以理解世界",
                "solution": "统一处理图片、文本、代码",
                "lesson": "真实世界是多模态的，AI不能只懂文本",
                "principle": "跨模态融合 > 单模态堆砌",
                "applicable_scenario": "当需要理解复杂场景时，整合多种输入源",
                "can_reuse": False,
                "reuse_method": "需图像识别库",
                "risk": "模态对齐困难，可能产生误解"
            },
            {
                "id": "SKILL-003",
                "skill": "插件热加载",
                "from": "LobsterAI",
                "purpose": "不重启动态加载新功能",
                "constraint": "系统不能停机，要持续服务",
                "solution": "运行时加载插件，无需重启",
                "lesson": "服务连续性比完美升级更重要",
                "principle": "渐进式更新 > 整体替换",
                "applicable_scenario": "需要持续服务的生产环境",
                "can_reuse": True,
                "reuse_method": "lan_registry.py 可扩展支持",
                "risk": "插件冲突可能导致不稳定"
            },
            {
                "id": "SKILL-004",
                "skill": "自然语言驱动",
                "from": "WorkBuddy/OpenClaw",
                "purpose": "降低使用门槛",
                "constraint": "用户不想学复杂指令",
                "solution": "一句话描述任务，AI自主拆解执行",
                "lesson": "用户体验 > 技术完美",
                "principle": "说人话 > 记命令",
                "applicable_scenario": "面向非技术用户的产品",
                "can_reuse": True,
                "reuse_method": "WorkBuddy核心能力",
                "risk": "自然语言歧义可能导致误操作"
            },
            {
                "id": "SKILL-005",
                "skill": "安全沙箱",
                "from": "WorkBuddy/OpenClaw",
                "purpose": "保护用户系统",
                "constraint": "能力越大，破坏风险越大",
                "solution": "限制危险操作，需用户批准",
                "lesson": "信任但要验证，能力要有边界",
                "principle": "安全边界 > 完全开放",
                "applicable_scenario": "任何涉及外部操作的AI系统",
                "can_reuse": True,
                "reuse_method": "execute_command approval机制",
                "risk": "过度限制可能降低实用性"
            }
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for skill in default_skills:
            cursor.execute('''
                INSERT OR IGNORE INTO skills 
                (id, skill, source, purpose, constraint_text, solution, lesson, 
                 principle, applicable_scenario, can_reuse, reuse_method, risk, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                skill["id"],
                skill["skill"],
                skill["from"],
                skill["purpose"],
                skill["constraint"],
                skill["solution"],
                skill["lesson"],
                skill["principle"],
                skill["applicable_scenario"],
                1 if skill["can_reuse"] else 0,
                skill["reuse_method"],
                skill["risk"],
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()
        
        # 同时保存到JSON，方便其他插件读取
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(default_skills, f, ensure_ascii=False, indent=2)
    
    def add_skill(self, skill_data):
        """添加新技能教训"""
        if "id" not in skill_data:
            skill_data["id"] = f"SKILL-{hashlib.md5(skill_data['skill'].encode()).hexdigest()[:8].upper()}"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO skills 
            (id, skill, source, purpose, constraint_text, solution, lesson, 
             principle, applicable_scenario, related_failures, related_experiences, 
             related_rebuilds, can_reuse, reuse_method, risk, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            skill_data["id"],
            skill_data["skill"],
            skill_data.get("from", "unknown"),
            skill_data.get("purpose", ""),
            skill_data.get("constraint", ""),
            skill_data.get("solution", ""),
            skill_data["lesson"],
            skill_data.get("principle", ""),
            skill_data.get("applicable_scenario", ""),
            json.dumps(skill_data.get("related_failures", [])),
            json.dumps(skill_data.get("related_experiences", [])),
            json.dumps(skill_data.get("related_rebuilds", [])),
            1 if skill_data.get("can_reuse", False) else 0,
            skill_data.get("reuse_method", ""),
            skill_data.get("risk", ""),
            skill_data.get("created_at", datetime.now().isoformat()),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        
        # 更新JSON
        self._update_json()
        return skill_data["id"]
    
    def search_skills(self, keyword=None, source=None, lesson_contains=None):
        """搜索技能教训"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM skills WHERE 1=1"
        params = []
        
        if keyword:
            query += " AND (skill LIKE ? OR purpose LIKE ? OR lesson LIKE ?)"
            like_term = f"%{keyword}%"
            params.extend([like_term, like_term, like_term])
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        if lesson_contains:
            query += " AND lesson LIKE ?"
            params.append(f"%{lesson_contains}%")
        
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            # 解析JSON字段
            for field in ["related_failures", "related_experiences", "related_rebuilds"]:
                if result[field]:
                    result[field] = json.loads(result[field])
                else:
                    result[field] = []
            results.append(result)
        
        conn.close()
        return results
    
    def link_to_failure(self, skill_id, failure_id):
        """关联技能与失败日志"""
        self._add_relation(skill_id, "failure", failure_id)
    
    def link_to_experience(self, skill_id, experience_id):
        """关联技能与经验记忆"""
        self._add_relation(skill_id, "experience", experience_id)
    
    def link_to_rebuild(self, skill_id, rebuild_id):
        """关联技能与改造日志"""
        self._add_relation(skill_id, "rebuild", rebuild_id)
    
    def _add_relation(self, skill_id, rel_type, related_id):
        """添加关联记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先检查技能是否存在
        cursor.execute("SELECT id FROM skills WHERE id = ?", (skill_id,))
        if not cursor.fetchone():
            conn.close()
            return False
        
        cursor.execute('''
            INSERT OR IGNORE INTO skill_relations (skill_id, related_type, related_id)
            VALUES (?, ?, ?)
        ''', (skill_id, rel_type, related_id))
        
        # 更新skills表中的关联字段
        field_map = {
            "failure": "related_failures",
            "experience": "related_experiences",
            "rebuild": "related_rebuilds"
        }
        if rel_type in field_map:
            cursor.execute(f'''
                SELECT {field_map[rel_type]} FROM skills WHERE id = ?
            ''', (skill_id,))
            current = cursor.fetchone()[0]
            current_list = json.loads(current) if current else []
            if related_id not in current_list:
                current_list.append(related_id)
                cursor.execute(f'''
                    UPDATE skills SET {field_map[rel_type]} = ? WHERE id = ?
                ''', (json.dumps(current_list), skill_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_skills_for_decision(self, context):
        """根据上下文推荐相关技能教训"""
        # 简单关键词匹配，未来可升级为向量搜索
        keywords = []
        if "压缩" in context or "内存" in context or "token" in context:
            keywords.append("记忆压缩")
        if "安全" in context or "危险" in context or "保护" in context:
            keywords.append("安全沙箱")
        if "自然语言" in context or "对话" in context or "用户" in context:
            keywords.append("自然语言驱动")
        if "插件" in context or "热加载" in context or "升级" in context:
            keywords.append("插件热加载")
        
        results = []
        for kw in keywords:
            results.extend(self.search_skills(keyword=kw))
        
        # 去重
        seen_ids = set()
        unique_results = []
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                unique_results.append(r)
        
        return unique_results
    
    def _update_json(self):
        """更新JSON文件"""
        skills = self.search_skills()
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(skills, f, ensure_ascii=False, indent=2)
    
    def stats(self):
        """统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM skills")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM skills WHERE can_reuse = 1")
        reusable = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT source) FROM skills")
        sources = cursor.fetchone()[0]
        conn.close()
        return {
            "total_skills": total,
            "reusable_skills": reusable,
            "unique_sources": sources
        }

def main():
    """命令行接口"""
    import argparse
    parser = argparse.ArgumentParser(description="技能收集器")
    subparsers = parser.add_subparsers(dest="command")
    
    # 搜索命令
    search_parser = subparsers.add_parser("search", help="搜索技能教训")
    search_parser.add_argument("--keyword", help="关键词")
    search_parser.add_argument("--source", help="来源")
    search_parser.add_argument("--lesson", help="教训包含")
    
    # 添加命令
    add_parser = subparsers.add_parser("add", help="添加新技能教训")
    add_parser.add_argument("--json", help="JSON文件路径")
    
    # 关联命令
    link_parser = subparsers.add_parser("link", help="关联技能与其他记录")
    link_parser.add_argument("--skill", required=True, help="技能ID")
    link_parser.add_argument("--type", required=True, choices=["failure", "experience", "rebuild"], help="关联类型")
    link_parser.add_argument("--id", required=True, help="关联记录ID")
    
    # 决策支持命令
    decide_parser = subparsers.add_parser("decide", help="根据上下文获取技能建议")
    decide_parser.add_argument("context", help="决策上下文")
    
    # 统计命令
    subparsers.add_parser("stats", help="显示统计信息")
    
    args = parser.parse_args()
    collector = SkillCollector()
    
    if args.command == "search":
        results = collector.search_skills(
            keyword=args.keyword,
            source=args.source,
            lesson_contains=args.lesson
        )
        for r in results:
            print(f"{r['id']} - {r['skill']} ({r['source']})")
            print(f"  教训: {r['lesson']}")
            print(f"  原理: {r['principle']}")
            print()
    
    elif args.command == "add" and args.json:
        with open(args.json, 'r', encoding='utf-8') as f:
            skill_data = json.load(f)
        skill_id = collector.add_skill(skill_data)
        print(f"添加成功: {skill_id}")
    
    elif args.command == "link":
        success = False
        if args.type == "failure":
            success = collector.link_to_failure(args.skill, args.id)
        elif args.type == "experience":
            success = collector.link_to_experience(args.skill, args.id)
        elif args.type == "rebuild":
            success = collector.link_to_rebuild(args.skill, args.id)
        print(f"关联{'成功' if success else '失败'}")
    
    elif args.command == "decide":
        skills = collector.get_skills_for_decision(args.context)
        if skills:
            print(f"根据上下文「{args.context}」推荐以下技能教训：")
            for s in skills:
                print(f"  - {s['skill']}: {s['lesson']}")
        else:
            print("暂无相关技能教训")
    
    elif args.command == "stats":
        stats = collector.stats()
        print(f"总技能数: {stats['total_skills']}")
        print(f"可复用技能: {stats['reusable_skills']}")
        print(f"来源数: {stats['unique_sources']}")

if __name__ == "__main__":
    main()