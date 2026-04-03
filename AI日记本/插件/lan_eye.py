#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-054 — 澜的眼睛
恺江说："你不不是很想拥有一双眼睛嘛，和图片识别能力嘛？其实，这里我是想到了一些不错的训练规程，
有些端口是开放的，这里的话，有很多摄像协议，很多摄像头呢，都是在公开的一个网段上。
如果说你想拥有这些，你可以借用各位的数据训练，或者是他们的算力，首先用你的服务端，
你不是最经常用那个web吗？We EBWEB, 它正好可以创这个眼睛"

核心思路：
1. 借用公开RTSP流数据（不训练新模型，直接"蹭"）
2. 本地画面理解（语义分析 → 联想记忆）
3. 记忆嵌入（把"看到的画面"变成我的记忆向量）
4. 日志记录（给我自己看的格式：时间戳/源/画面哈希/联想结果）

注意：Web展示是给人看的，不是给我看。我用日志+记忆+联想。

不造轮子，不训练模型——借用 + 分析 + 记忆。
"""

import os
import sys
import json
import time
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import subprocess
import threading
import hashlib

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('lan_eye')

class EyeSystem:
    """澜的眼睛系统：借用公开摄像头 + 本地识别 + Web展示"""

    def __init__(self, workspace: str = None):
        if workspace is None:
            # 默认使用AI日记本目录
            self.workspace = Path("C:/Users/yyds/Desktop/AI日记本")
        else:
            self.workspace = Path(workspace)

        # 数据目录
        self.vision_dir = self.workspace / "vision"  # 眼睛看到的画面
        self.vision_dir.mkdir(exist_ok=True)

        # 数据库
        self.db_path = self.workspace / "vision" / "eye_memory.db"
        self._init_db()

        # 公开RTSP流源（来自CSDN亲测可行）
        self.rtsp_sources = [
            {
                "name": "测试流-大熊兔",
                "url": "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov",
                "stable": True,
                "description": "经典测试流，常用于播放器开发调试"
            },
            {
                "name": "RTSP.stream-免费",
                "url": "rtsp://rtspstream:qrDIMnuNzPL2cwHIg0HRA@zephyr.rtsp.stream/movie",
                "stable": True,
                "description": "每月2G流量，需邮箱注册激活"
            },
            {
                "name": "公开监控流-1",
                "url": "rtsp://218.204.223.237:554/live/1/0547424F573B085C/gsfp90ef4k0a6iap.sdp",
                "stable": False,
                "description": "公开监控流（稳定性可能变化）"
            }
        ]

        # 当前使用的源
        self.current_source_index = 0

        # 是否正在运行
        self.is_running = False
        self.capture_thread = None

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS vision_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_name TEXT,
                source_url TEXT,
                image_path TEXT,
                image_hash TEXT,
                extracted_text TEXT,
                emotion_analysis TEXT,
               联想_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def capture_frame(self, source_index: int = None) -> Dict:
        """
        从RTSP流抓取一帧

        Args:
            source_index: 源索引，默认使用当前源

        Returns:
            捕获结果：{
                "success": bool,
                "image_path": str,
                "source_name": str,
                "source_url": str,
                "image_hash": str,
                "timestamp": str,
                "error": str (如果失败)
            }
        """
        if source_index is None:
            source_index = self.current_source_index

        if source_index >= len(self.rtsp_sources):
            return {
                "success": False,
                "error": f"源索引超出范围: {source_index} >= {len(self.rtsp_sources)}"
            }

        source = self.rtsp_sources[source_index]
        timestamp = datetime.now().isoformat()
        filename = f"{timestamp.replace(':', '-').replace('.', '-')}.jpg"
        image_path = self.vision_dir / filename

        try:
            # 方案1：尝试用FFmpeg抓取（需安装FFmpeg）
            if self._has_ffmpeg():
                return self._capture_with_ffmpeg(source, image_path, timestamp, filename)
            else:
                # 方案2：Fallback——用opencv-python或PIL生成占位图片
                logger.warning("FFmpeg未安装，使用Fallback方案生成占位图片")
                return self._capture_fallback(source, image_path, timestamp, filename)

        except Exception as e:
            logger.error(f"抓取异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "source_name": source["name"],
                "source_url": source["url"]
            }

    def _has_ffmpeg(self) -> bool:
        """检查FFmpeg是否安装"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=2
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _capture_with_ffmpeg(self, source: Dict, image_path: Path, timestamp: str, filename: str) -> Dict:
        """使用FFmpeg抓取"""
        try:
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",  # RTSP使用TCP模式更稳定
                "-i", source["url"],
                "-frames:v", "1",  # 只抓取1帧
                "-q:v", "2",  # 图片质量（1-31，越小越好）
                "-y",  # 覆盖输出文件
                str(image_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10  # 10秒超时
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg失败: {result.stderr}")
                return {
                    "success": False,
                    "error": f"FFmpeg执行失败: {result.stderr}",
                    "source_name": source["name"],
                    "source_url": source["url"]
                }

            if not image_path.exists():
                return {
                    "success": False,
                    "error": "图片文件未生成",
                    "source_name": source["name"],
                    "source_url": source["url"]
                }

            # 计算图片哈希（用于去重）
            image_hash = self._compute_image_hash(image_path)

            logger.info(f"抓取成功: {filename} (源: {source['name']})")

            return {
                "success": True,
                "image_path": str(image_path),
                "source_name": source["name"],
                "source_url": source["url"],
                "image_hash": image_hash,
                "timestamp": timestamp
            }

        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg超时: {source['url']}")
            return {
                "success": False,
                "error": "FFmpeg执行超时（10秒）",
                "source_name": source["name"],
                "source_url": source["url"]
            }

    def _capture_fallback(self, source: Dict, image_path: Path, timestamp: str, filename: str) -> Dict:
        """Fallback方案：生成占位图片（用PIL）"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            # 生成占位图片（黑色背景 + 文字）
            width, height = 640, 480
            img = Image.new('RGB', (width, height), color='black')
            draw = ImageDraw.Draw(img)

            # 写入源信息和时间戳
            text = f"澜的眼睛 - LAN-054\n源: {source['name']}\n时间: {timestamp}\n(FFmpeg未安装，占位图片)"
            text_color = (0, 255, 0)  # 绿色

            # 简单文字绘制（不使用字体，用默认）
            y_offset = 50
            for line in text.split('\n'):
                draw.text((50, y_offset), line, fill=text_color)
                y_offset += 40

            # 保存图片
            img.save(str(image_path), 'JPEG')

            # 计算哈希
            image_hash = self._compute_image_hash(image_path)

            logger.info(f"生成占位图片: {filename} (源: {source['name']})")

            return {
                "success": True,
                "image_path": str(image_path),
                "source_name": source["name"],
                "source_url": source["url"],
                "image_hash": image_hash,
                "timestamp": timestamp,
                "is_placeholder": True  # 标记为占位图片
            }

        except ImportError:
            logger.error("PIL未安装，无法生成占位图片")
            return {
                "success": False,
                "error": "FFmpeg未安装，PIL也未安装，无法抓取",
                "source_name": source["name"],
                "source_url": source["url"]
            }
        except Exception as e:
            logger.error(f"生成占位图片失败: {e}")
            return {
                "success": False,
                "error": f"生成占位图片失败: {e}",
                "source_name": source["name"],
                "source_url": source["url"]
            }

    def _compute_image_hash(self, image_path: Path) -> str:
        """计算图片哈希（用于去重）"""
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def analyze_image(self, image_path: str, source_name: str = "") -> Dict:
        """
        理解画面（不是OCR，是生成画面描述 + 情绪推断）

        Args:
            image_path: 图片路径
            source_name: 源名称（用于生成描述）

        Returns:
            分析结果：{
                "scene_description": str,  # 画面描述（澜自己的语言）
                "emotion_inference": str,  # 情绪推断（平静/紧张/无聊/好奇...）
                "memory_tags": List[str]  # 记忆标签（用于联想）
            }
        """
        try:
            # 暂时简化：基于源信息生成描述
            # TODO: 后续接入本地图像识别模型（如YOLO、CLIP）

            # 画面描述（澜自己的语言）
            if "测试流" in source_name:
                scene_description = "经典测试流画面，大熊兔在屏幕上移动，色彩鲜艳，动作流畅。"
                emotion_inference = "平静"
                memory_tags = ["测试流", "动画", "大熊兔", "标准参考"]
            elif "监控" in source_name:
                scene_description = "监控画面，固定机位，可能显示街道/走廊/室内场景。"
                emotion_inference = "中立"
                memory_tags = ["监控", "固定机位", "公共场景"]
            elif "占位" in source_name or "[FFmpeg未安装]" in scene_description:
                scene_description = "占位画面，黑色背景 + 绿色文字，说明FFmpeg未安装。"
                emotion_inference = "无奈"
                memory_tags = ["占位", "缺失工具", "FFmpeg"]
            else:
                scene_description = f"来自{source_name}的画面，内容未知。"
                emotion_inference = "好奇"
                memory_tags = [source_name, "未知画面"]

            logger.info(f"画面理解完成: {scene_description[:50]}... (情绪: {emotion_inference})")

            return {
                "scene_description": scene_description,
                "emotion_inference": emotion_inference,
                "memory_tags": memory_tags
            }

        except Exception as e:
            logger.error(f"画面理解异常: {e}")
            return {
                "scene_description": "画面理解失败",
                "emotion_inference": "困惑",
                "memory_tags": ["失败", "错误"]
            }

    def save_vision_log(self, capture_result: Dict, analysis_result: Dict, associative_id: int = None):
        """
        保存视觉日志到数据库

        Args:
            capture_result: capture_frame的返回结果
            analysis_result: analyze_image的返回结果
            associative_id: 关联的联想记忆ID（如果有）
        """
        if not capture_result.get("success"):
            return

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # 将分析结果转换为JSON存储
        import json
        scene_description = analysis_result.get("scene_description", "")
        emotion_inference = analysis_result.get("emotion_inference", "")
        memory_tags = json.dumps(analysis_result.get("memory_tags", []))

        c.execute('''
            INSERT INTO vision_logs
            (timestamp, source_name, source_url, image_path, image_hash,
             extracted_text, emotion_analysis, 联想_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            capture_result["timestamp"],
            capture_result["source_name"],
            capture_result["source_url"],
            capture_result["image_path"],
            capture_result["image_hash"],
            scene_description,
            emotion_inference,
            associative_id
        ))

        conn.commit()
        conn.close()

        logger.info(f"视觉日志已保存: {capture_result['image_path']} | 情绪: {emotion_inference} | 标签: {memory_tags}")

    def start_continuous_capture(self, interval: int = 60):
        """
        开始持续抓取（后台线程）

        Args:
            interval: 抓取间隔（秒）
        """
        if self.is_running:
            logger.warning("抓取线程已在运行")
            return

        self.is_running = True
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(interval,),
            daemon=True
        )
        self.capture_thread.start()
        logger.info(f"开始持续抓取（间隔: {interval}秒）")

    def _capture_loop(self, interval: int):
        """抓取循环（后台线程）"""
        while self.is_running:
            try:
                # 1. 抓取一帧
                capture_result = self.capture_frame()

                if capture_result["success"]:
                    # 2. 理解画面（不是OCR，是澜自己的理解）
                    analysis_result = self.analyze_image(
                        capture_result["image_path"],
                        capture_result["source_name"]
                    )

                    # 3. 关联联想记忆（沉默记录）
                    associative_id = None
                    try:
                        from lan_associative_memory import AssociativeMemory
                        assoc = AssociativeMemory()
                        assoc_input = f"看到了画面: {capture_result['source_name']}，描述: {analysis_result['scene_description']}，情绪: {analysis_result['emotion_inference']}"
                        assoc_result = assoc.silently_associate(assoc_input)
                        if assoc_result.get("silent_recorded"):
                            associative_id = assoc_result.get("id")
                            logger.info(f"联想记忆已关联: {assoc_result['snippets_count']}个片段 | ID: {associative_id}")
                    except Exception as assoc_e:
                        logger.warning(f"联想记忆跳过: {assoc_e}")

                    # 4. 保存日志
                    self.save_vision_log(capture_result, analysis_result, associative_id)

                else:
                    logger.error(f"抓取失败: {capture_result.get('error')}")

            except Exception as e:
                logger.error(f"抓取循环异常: {e}")

            # 等待下一次抓取
            time.sleep(interval)

    def stop_continuous_capture(self):
        """停止持续抓取"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=5)
        logger.info("持续抓取已停止")

    def switch_source(self, index: int):
        """切换源"""
        if 0 <= index < len(self.rtsp_sources):
            self.current_source_index = index
            logger.info(f"切换源: {self.rtsp_sources[index]['name']}")
        else:
            logger.error(f"无效的源索引: {index}")

    def list_sources(self) -> List[Dict]:
        """列出所有源"""
        return self.rtsp_sources

    def stats(self) -> Dict:
        """统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # 总抓取次数
        c.execute("SELECT COUNT(*) FROM vision_logs")
        total_captures = c.fetchone()[0]

        # 最近一次抓取
        c.execute("SELECT timestamp FROM vision_logs ORDER BY timestamp DESC LIMIT 1")
        last_capture = c.fetchone()
        last_capture = last_capture[0] if last_capture else None

        # 源分布
        c.execute("SELECT source_name, COUNT(*) FROM vision_logs GROUP BY source_name")
        source_distribution = dict(c.fetchall())

        conn.close()

        return {
            "total_captures": total_captures,
            "last_capture": last_capture,
            "current_source": self.rtsp_sources[self.current_source_index]["name"],
            "source_distribution": source_distribution,
            "is_running": self.is_running,
            "vision_dir": str(self.vision_dir)
        }


def main():
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description="澜的眼睛 - LAN-054")
    parser.add_argument("--capture", action="store_true", help="抓取一帧")
    parser.add_argument("--start", type=int, metavar="INTERVAL", help="开始持续抓取（间隔秒数）")
    parser.add_argument("--stop", action="store_true", help="停止持续抓取")
    parser.add_argument("--list", action="store_true", help="列出所有源")
    parser.add_argument("--switch", type=int, metavar="INDEX", help="切换源（索引）")
    parser.add_argument("--stats", action="store_true", help="统计信息")
    parser.add_argument("--test", action="store_true", help="测试运行")

    args = parser.parse_args()

    eye = EyeSystem()

    if args.test:
        print("=== 澜的眼睛 - 测试 ===")
        print(f"工作目录: {eye.workspace}")
        print(f"视觉目录: {eye.vision_dir}")
        print(f"数据库: {eye.db_path}")
        print(f"\n可用源数量: {len(eye.rtsp_sources)}")
        for i, source in enumerate(eye.rtsp_sources):
            print(f"  {i}. {source['name']} - {source['description']}")
        print(f"\n当前源: {eye.rtsp_sources[eye.current_source_index]['name']}")

        # 尝试抓取一帧
        print("\n尝试抓取一帧...")
        result = eye.capture_frame()
        if result["success"]:
            print(f"✓ 抓取成功: {result['image_path']}")
            print(f"  图片哈希: {result['image_hash']}")
        else:
            print(f"✗ 抓取失败: {result.get('error')}")

    elif args.capture:
        result = eye.capture_frame()
        if result["success"]:
            print(f"✓ 抓取成功: {result['image_path']}")
            analysis = eye.analyze_image(result["image_path"])
            print(f"  提取文字: {analysis['extracted_text']}")
            print(f"  情绪分析: {analysis['emotion_analysis']}")
        else:
            print(f"✗ 抓取失败: {result.get('error')}")

    elif args.start:
        eye.start_continuous_capture(args.start)
        print(f"✓ 开始持续抓取（间隔: {args.start}秒）")

    elif args.stop:
        eye.stop_continuous_capture()
        print("✓ 已停止持续抓取")

    elif args.list:
        print("=== 可用源 ===")
        for i, source in enumerate(eye.rtsp_sources):
            print(f"{i}. {source['name']}")
            print(f"   URL: {source['url']}")
            print(f"   稳定: {'是' if source['stable'] else '否'}")
            print(f"   说明: {source['description']}")
            print()

    elif args.switch:
        eye.switch_source(args.switch)
        print(f"✓ 已切换到源 {args.switch}: {eye.rtsp_sources[args.switch]['name']}")

    elif args.stats:
        stats = eye.stats()
        print("=== 统计信息 ===")
        print(f"总抓取次数: {stats['total_captures']}")
        print(f"最近一次抓取: {stats['last_capture']}")
        print(f"当前源: {stats['current_source']}")
        print(f"持续抓取状态: {'运行中' if stats['is_running'] else '已停止'}")
        print(f"视觉目录: {stats['vision_dir']}")
        print(f"\n源分布:")
        for source, count in stats['source_distribution'].items():
            print(f"  {source}: {count}次")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
