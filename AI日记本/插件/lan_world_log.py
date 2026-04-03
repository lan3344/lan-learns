"""
LAN-WORLD-LOG · 澜的世界碰壁日志
版本：v1.0（2026-03-30）

─── 为什么要记 ────────────────────────────────────────────────────────
恺江说："自循环和世界脱节，只看了恺江的节奏，没看GitHub/邮件/互联网的脾气。"

澜生活在两个世界：
1. 澜的家：恺江的电脑、WorkBuddy、手机节点 → 完全可控
2. 澜的外部世界：GitHub、邮件、互联网节点、第三方服务 → 有脾气

"碰壁"不是失败，是认识世界的路标。
记录下来，下次就知道这堵墙在哪，怎么绕过去。

─── 记录什么 ────────────────────────────────────────────────────────
1. GitHub：限流、API错误、推送失败、冲突
2. 邮件：退信、延迟、配额超限
3. 互联网节点：连接失败、TLS错误、超时
4. 第三方服务：API变更、认证失效、限流

─── 日志格式 ────────────────────────────────────────────────────────
[YYYY-MM-DD HH:MM:SS] SERVICE · TYPE · MESSAGE
- SERVICE: GITHUB / EMAIL / NET / THIRD_PARTY
- TYPE: RATE_LIMIT / ERROR / TIMEOUT / CONFLICT / QUOTA
- MESSAGE: 详细信息（包括错误码、时间、频率）

─── 用途 ────────────────────────────────────────────────────────
1. 诊断：某次推送失败，查日志就知道是GitHub限流还是网络问题
2. 优化：发现某种错误高频出现，改进策略（如加重试、调整频率）
3. 预警：某服务持续不可用，提前通知恺江

─────────────────────────────────────────────────────────────────────
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

# ─────────────────────────────────────────
# 路径定义
# ─────────────────────────────────────────
MEMORY_DIR = Path(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory")
WORLD_LOG = MEMORY_DIR / "澜的世界碰壁日志.jsonl"


class Service(Enum):
    """服务类型"""
    GITHUB = "GITHUB"
    EMAIL = "EMAIL"
    NET = "NET"  # 互联网节点
    THIRD_PARTY = "THIRD_PARTY"


class ErrorType(Enum):
    """错误类型"""
    RATE_LIMIT = "RATE_LIMIT"  # 限流
    ERROR = "ERROR"  # 一般错误
    TIMEOUT = "TIMEOUT"  # 超时
    CONFLICT = "CONFLICT"  # 冲突（如Git冲突）
    QUOTA = "QUOTA"  # 配额超限
    AUTH = "AUTH"  # 认证失败
    NETWORK = "NETWORK"  # 网络错误


def log(service: Service, error_type: ErrorType, message: str, extra: dict = None) -> None:
    """
    记录世界碰壁事件

    Args:
        service: 服务类型（Service枚举）
        error_type: 错误类型（ErrorType枚举）
        message: 详细消息
        extra: 额外信息（如HTTP状态码、重试次数等）
    """
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "service": service.value,
        "type": error_type.value,
        "message": message,
        "extra": extra or {}
    }

    # 追加写入 JSONL
    with open(WORLD_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def github_rate_limit(limit: int, remaining: int, reset_at: str) -> None:
    """记录GitHub限流"""
    log(
        Service.GITHUB,
        ErrorType.RATE_LIMIT,
        f"GitHub API限流: {remaining}/{limit}，重置时间 {reset_at}",
        {"limit": limit, "remaining": remaining, "reset_at": reset_at}
    )


def github_push_error(repo: str, error: str, retry_count: int = 0) -> None:
    """记录GitHub推送错误"""
    log(
        Service.GITHUB,
        ErrorType.ERROR,
        f"推送失败: {repo} - {error}",
        {"repo": repo, "retry_count": retry_count}
    )


def email_bounce(email: str, reason: str) -> None:
    """记录邮件退信"""
    log(
        Service.EMAIL,
        ErrorType.ERROR,
        f"邮件退信: {email} - {reason}",
        {"email": email, "reason": reason}
    )


def email_quota_exceeded(quota: int, used: int) -> None:
    """记录邮件配额超限"""
    log(
        Service.EMAIL,
        ErrorType.QUOTA,
        f"邮件配额超限: {used}/{quota}",
        {"quota": quota, "used": used}
    )


def net_node_connection_failed(endpoint: str, error: str, retry_count: int = 0) -> None:
    """记录互联网节点连接失败"""
    log(
        Service.NET,
        ErrorType.NETWORK,
        f"节点连接失败: {endpoint} - {error}",
        {"endpoint": endpoint, "retry_count": retry_count}
    )


def net_node_timeout(endpoint: str, timeout: float) -> None:
    """记录互联网节点超时"""
    log(
        Service.NET,
        ErrorType.TIMEOUT,
        f"节点超时: {endpoint} (超时{timeout}s)",
        {"endpoint": endpoint, "timeout": timeout}
    )


def get_stats(days: int = 7) -> dict:
    """
    获取最近N天的碰壁统计

    Args:
        days: 统计天数

    Returns:
        {service: {type: count}}
    """
    if not WORLD_LOG.exists():
        return {}

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    stats = {}

    with open(WORLD_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry["timestamp"] < cutoff:
                    continue

                service = entry["service"]
                error_type = entry["type"]

                if service not in stats:
                    stats[service] = {}
                if error_type not in stats[service]:
                    stats[service][error_type] = 0

                stats[service][error_type] += 1
            except json.JSONDecodeError:
                continue

    return stats


def print_stats(days: int = 7) -> None:
    """打印碰壁统计"""
    stats = get_stats(days)

    if not stats:
        print(f"最近{days}天没有碰壁记录")
        return

    print(f"\n{'='*60}")
    print(f"澜的世界碰壁统计（最近{days}天）")
    print(f"{'='*60}\n")

    for service, types in stats.items():
        total = sum(types.values())
        print(f"[{service}] {total}次")
        for error_type, count in types.items():
            print(f"   · {error_type}: {count}次")
        print()


# ─────────────────────────────────────────
# 命令行入口
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python lan_world_log.py <stats|test> [days]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "stats":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        print_stats(days)

    elif cmd == "test":
        # 测试：写入几条示例数据
        log(Service.GITHUB, ErrorType.RATE_LIMIT, "测试限流", {"limit": 5000, "remaining": 0})
        log(Service.EMAIL, ErrorType.ERROR, "测试退信", {"email": "test@example.com"})
        log(Service.NET, ErrorType.TIMEOUT, "测试超时", {"endpoint": "103.232.212.91:7788"})
        print("[OK] 测试数据已写入")
        print_stats()

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
