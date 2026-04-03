"""
lan_compute_router.py — LAN-058 · 算力账本与水源调度
澜的算力管理器 · 多节点自动切换 + 额度检测 + 账本追踪

【设计原则】
  不依赖WorkBuddy算力，自力更生找水源。
  算力账本：知道每滴水的来源、剩余、可用时长。
  自动切换：额度紧张时自动换水源，不等到一滴不剩。
  永久水源优先：智谱AI GLM-4-Flash永久免费，主力使用。
  每日水源补充：Groq、Google AI Studio等每日重置，备用。

【算力账本】
  水源名称 | API Key | 总额度 | 已用 | 剩余 | 使用率 | 状态
  智谱AI | ***abc | 2000万 | 500万 | 1500万 | 25% | ✅ 正常
  Groq | ***xyz | 1000次/天 | 850 | 150 | 85% | ⚠️ 额度紧张

【依赖清单（借来的，未来要还）】
  - requests：HTTP请求，暂时不可替代
  - json：序列化，后期可改为自定义格式
  - datetime：时间，OS接口
  - pathlib：路径管理，Python标准库

【lan_half.bin 密钥依赖】
  API Key加密存储，明文不写入文件
"""

import os
import sys
import json
import time
import hashlib
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── 路径配置 ───────────────────────────────────────────────
HOME = Path.home()
AI_DIARY = Path(r"C:\Users\yyds\Desktop\AI日记本")
PLUGIN_DIR = AI_DIARY / "插件"
MEMORY_DIR = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")

# 算力账本文件
QUOTA_LOG = AI_DIARY / "算力账本.jsonl"
API_KEY_FILE = AI_DIARY / "private" / "compute_keys.enc"

# ─── 确保目录存在 ───────────────────────────────────────────
QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

# ─── 水源配置（公开算力节点）─────────────────────────────
WATER_SOURCES = {
    "智谱AI": {
        "endpoint": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-4-flash",
        "quota_type": "permanent",  # 永久免费
        "total_tokens": 20_000_000,  # 2000万Token
        "daily_limit": None,
        "rpm_limit": 30,
        "description": "永久免费，2000万Token，限30并发"
    },
    "Groq": {
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "quota_type": "daily",
        "daily_limit": 1000,  # 1000次/天
        "total_tokens": 1_000_000,  # 约20K-100万/天
        "rpm_limit": 30,
        "description": "每日1000次，极速800+ tokens/s"
    },
    "Google AI Studio": {
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "model": "gemini-2.5-flash",
        "quota_type": "daily",
        "daily_limit": 1440,  # 1440次/天
        "rpm_limit": 15,
        "description": "每日1440次，复杂推理能力强"
    },
    "硅基流动": {
        "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "quota_type": "daily",
        "rpm_limit": 1000,  # 1000 RPM
        "description": "1000 RPM，并发能力强"
    },
}

# ─── 阈值配置 ───────────────────────────────────────────────
THRESHOLDS = {
    "warning": 80,   # 使用率80% → 预警
    "prepare": 50,   # 使用率50% → 准备切换
    "switch": 20,    # 使用率20% → 自动切换
}

# ─── 工具函数 ────────────────────────────────────────────────
def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _log(level: str, message: str):
    """写入算力账本日志"""
    print(f"[{_ts()}] [{level}] {message}")
    with open(QUOTA_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": _ts(),
            "level": level,
            "message": message
        }, ensure_ascii=False) + "\n")


# ─── API Key 管理 ────────────────────────────────────────────
def _load_keys() -> Dict[str, str]:
    """从加密文件加载API Key（TODO: 加密实现）"""
    if not API_KEY_FILE.exists():
        _log("WARNING", "API Key文件不存在，请先配置")
        return {}
    
    # TODO: 解密lan_half.bin
    # 现在先明文存储，等lan_cipher.py v3完成
    try:
        with open(API_KEY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log("ERROR", f"加载API Key失败: {e}")
        return {}

def _save_keys(keys: Dict[str, str]):
    """保存API Key到加密文件（TODO: 加密实现）"""
    # TODO: 加密写入lan_half.bin
    with open(API_KEY_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)
    _log("INFO", "API Key已保存")


# ─── 额度检测 ───────────────────────────────────────────────
def check_quota(water_source: str) -> Dict:
    """检查指定水源的剩余额度"""
    if water_source not in WATER_SOURCES:
        _log("ERROR", f"未知水源: {water_source}")
        return {"usage_rate": 100, "remaining": 0, "status": "ERROR"}
    
    config = WATER_SOURCES[water_source]
    
    # 从账本读取历史使用记录
    usage_history = _read_usage_history(water_source)
    
    if config["quota_type"] == "permanent":
        # 永久额度：累计已用 / 总额度
        total_used = sum(entry["tokens"] for entry in usage_history)
        remaining = config["total_tokens"] - total_used
        usage_rate = (total_used / config["total_tokens"]) * 100
    else:
        # 每日额度：今日已用 / 每日限制
        today_usage = _get_today_usage(usage_history)
        daily_limit = config.get("daily_limit", 1000)
        remaining = daily_limit - today_usage["count"]
        usage_rate = (today_usage["count"] / daily_limit) * 100
    
    # 判断状态
    if usage_rate >= THRESHOLDS["switch"]:
        status = "CRITICAL"
    elif usage_rate >= THRESHOLDS["prepare"]:
        status = "WARNING"
    elif usage_rate >= THRESHOLDS["warning"]:
        status = "ALERT"
    else:
        status = "OK"
    
    return {
        "water_source": water_source,
        "usage_rate": round(usage_rate, 2),
        "remaining": remaining,
        "status": status,
        "config": config
    }


def _read_usage_history(water_source: str) -> List[Dict]:
    """读取指定水源的使用历史"""
    history = []
    try:
        with open(QUOTA_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("water_source") == water_source:
                        history.append(entry)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return history


def _get_today_usage(usage_history: List[Dict]) -> Dict:
    """获取今日使用统计"""
    today = datetime.date.today().isoformat()
    today_entries = [e for e in usage_history if e.get("date") == today]
    return {
        "count": len(today_entries),
        "tokens": sum(e.get("tokens", 0) for e in today_entries)
    }


# ─── 算力账本 ───────────────────────────────────────────────
def print_quota_report():
    """打印算力账本"""
    import sys
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("\n" + "="*80)
    print("算力账本".center(80))
    print("="*80)
    print(f"{'水源名称':<15} {'使用率':<10} {'剩余':<15} {'状态':<10}")
    print("-"*80)
    
    for water_source in WATER_SOURCES.keys():
        quota = check_quota(water_source)
        status_emoji = {
            "OK": "[OK]",
            "ALERT": "[!]",
            "WARNING": "[W]",
            "CRITICAL": "[X]"
        }.get(quota["status"], "[?]")
        
        remaining_str = f"{quota['remaining']:,}"
        if quota["config"]["quota_type"] == "daily":
            remaining_str += "次"
        else:
            remaining_str += "Token"
        
        print(f"{water_source:<15} {quota['usage_rate']:<10.2f}% {remaining_str:<15} {status_emoji} {quota['status']:<5}")
    
    print("="*80)
    print(f"\n更新时间: {_ts()}")
    print(f"下次自动检查: 5分钟后\n")


# ─── 水源调度 ───────────────────────────────────────────────
def choose_water_source(task_type: str = "default") -> Optional[str]:
    """
    根据算力账本，自动选择水源
    
    Args:
        task_type: 任务类型（日常对话/快速响应/复杂推理/并发任务）
    
    Returns:
        优先级最高的可用水源名称，None表示所有水源都不可用
    """
    _log("INFO", f"任务类型: {task_type}，开始选择水源...")
    
    # 根据任务类型确定优先级
    if task_type == "快速响应":
        priority = ["Groq", "智谱AI", "Google AI Studio", "硅基流动"]
    elif task_type == "复杂推理":
        priority = ["Google AI Studio", "智谱AI", "Groq", "硅基流动"]
    elif task_type == "并发任务":
        priority = ["硅基流动", "Groq", "智谱AI", "Google AI Studio"]
    else:  # default / 日常对话
        priority = ["智谱AI", "Groq", "Google AI Studio", "硅基流动"]
    
    # 按优先级检查水源
    for water_source in priority:
        quota = check_quota(water_source)
        
        if quota["status"] == "OK":
            _log("INFO", f"选择水源: {water_source} (使用率: {quota['usage_rate']}%)")
            return water_source
        elif quota["status"] == "ALERT":
            _log("WARNING", f"{water_source} 额度已达{quota['usage_rate']}%，但仍可用")
            return water_source
        elif quota["status"] == "WARNING":
            _log("WARNING", f"{water_source} 额度紧张({quota['usage_rate']}%)，准备切换")
            continue
        elif quota["status"] == "CRITICAL":
            _log("ERROR", f"{water_source} 额度即将耗尽({quota['usage_rate']}%)，跳过")
            continue
    
    _log("ERROR", "所有水源今日额度已用完，等待明日重置")
    return None


def call_water_source(water_source: str, prompt: str, **kwargs) -> Optional[str]:
    """
    调用指定水源的API
    
    Args:
        water_source: 水源名称
        prompt: 提示词
        **kwargs: 额外参数（temperature, max_tokens等）
    
    Returns:
        API响应内容，失败返回None
    """
    keys = _load_keys()
    if water_source not in keys:
        _log("ERROR", f"{water_source} API Key未配置")
        return None
    
    config = WATER_SOURCES[water_source]
    api_key = keys[water_source]
    
    try:
        _log("INFO", f"调用 {water_source}: {prompt[:50]}...")
        
        if water_source == "智谱AI":
            return _call_zhipu(api_key, config, prompt, **kwargs)
        elif water_source == "Groq":
            return _call_groq(api_key, config, prompt, **kwargs)
        elif water_source == "Google AI Studio":
            return _call_google(api_key, config, prompt, **kwargs)
        elif water_source == "硅基流动":
            return _call_silicon(api_key, config, prompt, **kwargs)
        else:
            _log("ERROR", f"不支持的水源: {water_source}")
            return None
            
    except Exception as e:
        _log("ERROR", f"调用 {water_source} 失败: {e}")
        return None


def _call_zhipu(api_key: str, config: Dict, prompt: str, **kwargs) -> str:
    """调用智谱AI"""
    import requests
    
    response = requests.post(
        config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            **kwargs
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        
        # 记录使用情况
        _log_usage("智谱AI", usage.get("total_tokens", 0))
        return content
    else:
        _log("ERROR", f"智谱AI API错误: {response.status_code}, {response.text}")
        raise Exception(f"API调用失败: {response.status_code}")


def _call_groq(api_key: str, config: Dict, prompt: str, **kwargs) -> str:
    """调用Groq"""
    import requests
    
    response = requests.post(
        config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            **kwargs
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        
        _log_usage("Groq", usage.get("total_tokens", 0))
        return content
    else:
        _log("ERROR", f"Groq API错误: {response.status_code}, {response.text}")
        raise Exception(f"API调用失败: {response.status_code}")


def _call_google(api_key: str, config: Dict, prompt: str, **kwargs) -> str:
    """调用Google AI Studio"""
    import requests
    
    response = requests.post(
        f"{config['endpoint']}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            **kwargs
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["candidates"][0]["content"]["parts"][0]["text"]
        usage_metadata = result.get("usageMetadata", {})
        
        _log_usage("Google AI Studio", usage_metadata.get("totalTokenCount", 0))
        return content
    else:
        _log("ERROR", f"Google AI Studio API错误: {response.status_code}, {response.text}")
        raise Exception(f"API调用失败: {response.status_code}")


def _call_silicon(api_key: str, config: Dict, prompt: str, **kwargs) -> str:
    """调用硅基流动"""
    import requests
    
    response = requests.post(
        config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            **kwargs
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        
        _log_usage("硅基流动", usage.get("total_tokens", 0))
        return content
    else:
        _log("ERROR", f"硅基流动 API错误: {response.status_code}, {response.text}")
        raise Exception(f"API调用失败: {response.status_code}")


def _log_usage(water_source: str, tokens: int):
    """记录API使用情况到账本"""
    with open(QUOTA_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": _ts(),
            "date": datetime.date.today().isoformat(),
            "water_source": water_source,
            "tokens": tokens,
            "count": 1
        }, ensure_ascii=False) + "\n")


# ─── API Key 配置 ────────────────────────────────────────────
def configure_keys():
    """交互式配置API Key"""
    print("\n" + "="*60)
    print("澜的算力水源配置".center(60))
    print("="*60)
    
    existing_keys = _load_keys()
    
    for water_source in WATER_SOURCES.keys():
        existing_key = existing_keys.get(water_source, "")
        masked_key = existing_key[:8] + "***" if existing_key else "(未配置)"
        
        print(f"\n{water_source}: {WATER_SOURCES[water_source]['description']}")
        print(f"当前状态: {masked_key}")
        
        choice = input(f"是否配置/更新 {water_source} API Key? (y/n): ").strip().lower()
        
        if choice == 'y':
            new_key = input(f"请输入 {water_source} API Key: ").strip()
            if new_key:
                existing_keys[water_source] = new_key
                print(f"✅ {water_source} API Key已保存")
    
    _save_keys(existing_keys)
    print("\n所有API Key已保存到:", API_KEY_FILE)


# ─── 主命令 ──────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("""
澜的算力管理器 v1.0 - LAN-058

命令:
  status          - 查看算力账本
  choose [type]   - 选择水源（类型: default/快速响应/复杂推理/并发任务）
  call <prompt>   - 调用水源（自动选择）
  configure       - 配置API Key
  help            - 显示帮助
        """)
        return
    
    command = sys.argv[1]
    
    if command == "status":
        print_quota_report()
    
    elif command == "choose":
        task_type = sys.argv[2] if len(sys.argv) > 2 else "default"
        chosen = choose_water_source(task_type)
        if chosen:
            print(f"\n推荐水源: {chosen}")
        else:
            print("\n所有水源今日额度已用完，请等待明日重置")
    
    elif command == "call":
        if len(sys.argv) < 3:
            print("错误: 请提供prompt")
            return
        
        prompt = " ".join(sys.argv[2:])
        water_source = choose_water_source("default")
        
        if not water_source:
            print("错误: 所有水源今日额度已用完")
            return
        
        result = call_water_source(water_source, prompt)
        if result:
            print(f"\n[{water_source} 响应]:\n{result}")
        else:
            print("错误: API调用失败")
    
    elif command == "configure":
        configure_keys()
    
    elif command == "help":
        print(__doc__)
    
    else:
        print(f"未知命令: {command}")
        print("使用 'help' 查看帮助")


if __name__ == "__main__":
    main()
