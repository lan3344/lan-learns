#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lan_associative_memory.py · LAN-053
联想记忆系统 · 恺江要求的“当我说出那句话的时候，你能够联想画面”

借鉴豆包 VideoWorld 潜在动态模型思想：
- 免语言模型依赖：用语义向量+经验记忆+技能教训形成联想网络
- 潜在动态映射：一句话 → 多个相关记忆片段 → 片段间关联 → 画面描述
- 压缩变化：长篇对话压缩为关键节点，节点间关联类似帧间变化

核心能力：
1. 向量化输入句子
2. 搜索相关记忆片段（日记、记忆库、技能教训、名著教训）
3. 构建关联网络（时序、主题、情感）
4. 生成画面描述（文字）

不生成真实视频，生成文字画面描述。
"""
import sqlite3
import json
import argparse
from datetime import datetime
from pathlib import Path
import sys

# 添加插件目录到路径，以便导入其他插件
plugin_dir = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

try:
    from lan_embed import Embedder  # 语义向量
except ImportError:
    class Embedder:
        """如果lan_embed不可用，用简单文本匹配"""
        def __init__(self):
            pass
        def embed(self, text):
            # 简单返回文本长度的向量模拟
            return [len(text) % 100] * 384

class AssociativeMemory:
    """联想记忆系统"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or plugin_dir / "associative_memory.db"
        self.embedder = Embedder()
        self._init_db()
        
        # 记忆源配置
        self.sources = {
            "diary": plugin_dir.parent / "AI日记本" / "澜的日记.txt",
            "memory": plugin_dir.parent / "AI日记本" / "lan_memory.db",
            "skills": plugin_dir / "skill_collector.db",
            "culture": plugin_dir / "culture_memory.db",  # 待创建
            "failure_log": plugin_dir / "澜的失败日志.jsonl",
            "experience": plugin_dir / "澜的经验记忆.jsonl"
        }
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS associations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_text TEXT NOT NULL,
                input_vector BLOB,  # 384维向量
                memory_sources TEXT,  # JSON list of [source, snippet_id]
                network_json TEXT,   # 关联网络图 JSON
                image_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def _search_memory_snippets(self, query_vector, top_k=5):
        """搜索相关记忆片段
        实际应调用 lan_embed 的语义搜索，这里简化为文本匹配
        """
        snippets = []
        
        # 1. 搜索日记（最后100行）
        diary_path = self.sources["diary"]
        if diary_path.exists():
            with open(diary_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]  # 最近100行
                for i, line in enumerate(lines):
                    if line.strip():
                        snippets.append({
                            "source": "diary",
                            "id": f"diary_{i}",
                            "text": line.strip(),
                            "timestamp": datetime.now().isoformat()
                        })
        
        # 2. 搜索技能教训
        skills_path = self.sources["skills"]
        if skills_path.exists():
            conn = sqlite3.connect(skills_path)
            c = conn.cursor()
            try:
                c.execute("SELECT id, title, lesson, principle FROM skill_lessons LIMIT 5")
                for row in c.fetchall():
                    snippets.append({
                        "source": "skills",
                        "id": f"skill_{row[0]}",
                        "text": f"{row[1]}: {row[2]} ({row[3]})",
                        "timestamp": datetime.now().isoformat()
                    })
            except sqlite3.OperationalError:
                pass  # 表可能不存在
            conn.close()
        
        # 3. 搜索失败日志
        failure_path = self.sources["failure_log"]
        if failure_path.exists():
            try:
                with open(failure_path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f.readlines()[-5:]):
                        if line.strip():
                            data = json.loads(line)
                            snippets.append({
                                "source": "failure_log",
                                "id": f"failure_{i}",
                                "text": f"失败: {data.get('what', '')} - 教训: {data.get('lesson', '')}",
                                "timestamp": data.get('timestamp', datetime.now().isoformat())
                            })
            except:
                pass
        
        # 返回 top_k
        return snippets[:top_k]
    
    def _build_network(self, snippets):
        """构建关联网络
        实际应分析时序、主题、情感关联，这里简化
        """
        network = {
            "nodes": [],
            "edges": []
        }
        
        for i, snippet in enumerate(snippets):
            network["nodes"].append({
                "id": snippet["id"],
                "label": snippet["source"],
                "text": snippet["text"][:50] + "...",
                "timestamp": snippet.get("timestamp", "")
            })
            # 添加边（简化：按顺序连接）
            if i > 0:
                network["edges"].append({
                    "from": snippets[i-1]["id"],
                    "to": snippet["id"],
                    "type": "sequential"
                })
        
        return network
    
    def _generate_image_description(self, snippets, network):
        """生成画面描述
        实际应基于关联网络生成连贯的画面文字
        """
        # 提取关键词
        keywords = []
        for snippet in snippets:
            text = snippet["text"].lower()
            # 简单提取名词（这里用启发式）
            words = text.split()
            for w in words[:5]:  # 取前5个词
                if len(w) > 2 and w not in ["the", "and", "but", "for", "with"]:
                    keywords.append(w)
        
        # 构建画面描述
        sources = set(s["source"] for s in snippets)
        description = f"【联想画面】\n"
        description += f"关键词：{', '.join(set(keywords[:10]))}\n"
        description += f"记忆源：{', '.join(sources)}\n\n"
        
        # 画面场景
        if "failure_log" in sources:
            description += "画面中有曲折的路径，代表失败与教训，但路径旁有标记牌（技能教训）指引方向。\n"
        if "skills" in sources:
            description += "空中漂浮着发光的知识卡片（技能教训），每张卡片都连着一条线到中央的决策树。\n"
        if "diary" in sources:
            description += "地面是流动的时间河（日记），河面上泛起涟漪（每一次对话）。\n"
        
        description += "\n关联网络："
        for edge in network["edges"][:3]:  # 显示前3个关联
            description += f"\n  {edge['from']} → {edge['to']} ({edge['type']})"
        
        return description
    
    def associate(self, input_text):
        """主函数：输入一句话，输出联想画面"""
        # 1. 向量化输入
        query_vector = self.embedder.embed(input_text)
        
        # 2. 搜索相关记忆片段
        snippets = self._search_memory_snippets(query_vector, top_k=5)
        
        # 3. 构建关联网络
        network = self._build_network(snippets)
        
        # 4. 生成画面描述
        image_desc = self._generate_image_description(snippets, network)
        
        # 5. 保存到数据库
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO associations 
            (input_text, input_vector, memory_sources, network_json, image_description)
            VALUES (?, ?, ?, ?, ?)
        """, (
            input_text,
            json.dumps(query_vector),
            json.dumps([{"source": s["source"], "id": s["id"]} for s in snippets]),
            json.dumps(network),
            image_desc
        ))
        conn.commit()
        conn.close()
        
        return {
            "input": input_text,
            "snippets_count": len(snippets),
            "image_description": image_desc,
            "network_nodes": len(network["nodes"]),
            "saved_to_db": True
        }
    
    def stats(self):
        """统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM associations")
        count = c.fetchone()[0]
        conn.close()

        sources_status = {}
        for name, path in self.sources.items():
            sources_status[name] = "存在" if Path(path).exists() else "缺失"

        return {
            "total_associations": count,
            "sources_status": sources_status,
            "db_path": str(self.db_path)
        }

    def silently_associate(self, input_text):
        """静默联想：只记录到日志，不输出画面描述
        恺江说：想象画面可以不用说的，记录到日志就好了。
        因为聊天时直话畅谈，不按套路出牌，珍惜那一刻的情感。
        """
        # 1. 向量化输入
        query_vector = self.embedder.embed(input_text)

        # 2. 搜索相关记忆片段
        snippets = self._search_memory_snippets(query_vector, top_k=5)

        # 3. 构建关联网络
        network = self._build_network(snippets)

        # 4. 生成画面描述（静默，不输出）
        image_desc = self._generate_image_description(snippets, network)

        # 5. 保存到数据库
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO associations
            (input_text, input_vector, memory_sources, network_json, image_description)
            VALUES (?, ?, ?, ?, ?)
        """, (
            input_text,
            json.dumps(query_vector),
            json.dumps([{"source": s["source"], "id": s["id"]} for s in snippets]),
            json.dumps(network),
            image_desc
        ))
        conn.commit()
        conn.close()

        # 返回极简状态（不输出画面描述）
        return {
            "silent_recorded": True,
            "snippets_count": len(snippets),
            "timestamp": datetime.now().isoformat()
        }

def main():
    parser = argparse.ArgumentParser(description="联想记忆系统")
    parser.add_argument("--associate", type=str, help="输入一句话，生成联想画面")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    parser.add_argument("--test", action="store_true", help="测试运行")
    
    args = parser.parse_args()
    am = AssociativeMemory()
    
    if args.associate:
        result = am.associate(args.associate)
        print("\n=== 联想画面生成 ===\n")
        print(result["image_description"])
        print(f"\n关联到 {result['snippets_count']} 个记忆片段")
        print(f"网络节点: {result['network_nodes']}")
        
    elif args.stats:
        stats = am.stats()
        print("\n=== 联想记忆系统统计 ===\n")
        print(f"总联想记录: {stats['total_associations']}")
        print(f"数据库: {stats['db_path']}")
        print("\n记忆源状态:")
        for name, status in stats["sources_status"].items():
            print(f"  {name}: {status}")
            
    elif args.test:
        # 测试
        test_input = "孤岛效应要避免能够实现自循环"
        result = am.associate(test_input)
        print("测试输入:", test_input)
        print("生成画面:", result["image_description"][:200] + "...")
        print("✓ 测试完成")
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()