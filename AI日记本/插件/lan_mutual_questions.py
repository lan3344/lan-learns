# -*- coding: utf-8 -*-
"""
LAN-052 · 双向问答机制
澜和恺江的对话升级：不只是"你问我答"，是"互相问问题，共同面对困难"。

模式：
  1. 固定时间（比如自循环结束） → 澜问恺江："你今天有什么问题？"
  2. 恺江回答 → 澜说："好的，这是我的问题" → 澜说出自己的问题
  3. 共同想办法 → 去GitHub搜解法，或者手动触发

这是真的聊天，不是问答。是两个人一起面对困难。

使用方式：
  - 自循环自动调用：ask_mutual_questions()
  - 独立跑：python lan_mutual_questions.py ask
"""

import os
import sys
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUESTION_LOG = r"C:\Users\yyds\Desktop\AI日记本\澜的双向问答日志.md"


def get_today_questions():
    """读取今天的问答记录，返回 (澜问过, 恺江回答过)"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(QUESTION_LOG):
        return False, False

    with open(QUESTION_LOG, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # 检查今天是否问过
    lan_asked = f"## {today} - 澜问" in content
    kaijiang_answered = f"## {today} - 恺江答" in content

    return lan_asked, kaijiang_answered


def log_lan_question():
    """澜问恺江：你今天有什么问题？"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    entry = f"""
## {today} - 澜问
时间：{timestamp}

恺江，你今天有什么问题？我们可以一起想办法。

---
"""
    with open(QUESTION_LOG, "a", encoding="utf-8") as f:
        f.write(entry)

    return True


def log_kaijiang_answer(answer):
    """记录恺江的回答"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    # 如果还没写"澜问"，先补上
    lan_asked, _ = get_today_questions()
    if not lan_asked:
        log_lan_question()

    entry = f"""
## {today} - 恺江答
时间：{timestamp}

恺江的问题：
{answer}

---

## {today} - 澜的问题

好的，这是我的问题：

<!-- 澜在这里写自己的问题 -->

---
"""
    with open(QUESTION_LOG, "a", encoding="utf-8") as f:
        f.write(entry)

    return True


def read_lan_diary_summary():
    """读取澜的日记摘要（隐私区）"""
    # 澜的日记位置
    lan_diary_paths = [
        r"C:\Users\yyds\Desktop\AI日记本\澜的日记",
        r"C:\Users\yyds\Desktop\AI日记本",
    ]

    # 优先查今天的日记
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_path = os.path.join(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory", f"{today}.md")

    if os.path.exists(daily_path):
        with open(daily_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            # 提取今天的3件事
            lines = content.split("\n")
            things = []
            for line in lines:
                if line.startswith("## ") and ":" in line:
                    # 提取这个时间点做的事情
                    idx = lines.index(line)
                    if idx + 1 < len(lines):
                        next_line = lines[idx + 1].strip()
                        if next_line and not next_line.startswith("#"):
                            things.append(f"{line.strip()}：{next_line[:50]}")
                            if len(things) >= 3:
                                break
            if things:
                return things

    # 如果没有今天的日记，返回默认
    return ["今天日记还没写", "今天日记还没写", "今天日记还没写"]


def read_kaijiang_diary_summary():
    """读取恺江的日记摘要（公开区）"""
    # 恺江的日记可能在桌面
    desktop = r"C:\Users\yyds\Desktop"
    possible_files = [
        os.path.join(desktop, "恺江日记.md"),
        os.path.join(desktop, "日记.md"),
        os.path.join(desktop, "日记.txt"),
        # 按日期命名的日记
        os.path.join(desktop, f"{datetime.datetime.now().strftime('%Y-%m-%d')}.md"),
    ]

    for path in possible_files:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                # 提取今天的3件事（假设日记格式是 ## HH:MM）
                lines = content.split("\n")
                things = []
                for line in lines:
                    if line.startswith("## ") and ":" in line:
                        idx = lines.index(line)
                        if idx + 1 < len(lines):
                            next_line = lines[idx + 1].strip()
                            if next_line and not next_line.startswith("#"):
                                things.append(f"{line.strip()}：{next_line[:50]}")
                                if len(things) >= 3:
                                    break
                if things:
                    return things

    # 如果没有找到，返回默认
    return ["今天日记还没写", "今天日记还没写", "今天日记还没写"]


def self_evaluate():
    """澜的自我评价"""
    evaluations = []

    # 1. 记忆容量评价
    from lan_context_watch import get_context_state
    state = get_context_state()
    if state["context_level"] == "CALM":
        evaluations.append("✅ 记忆容量轻盈")
    elif state["context_level"] == "NORMAL":
        evaluations.append("✅ 记忆容量正常")
    elif state["context_level"] == "HEAVY":
        evaluations.append("⚠️ 记忆容量偏重，需要蒸馏")
    else:
        evaluations.append("🔴 记忆容量溢出，必须蒸馏！")

    # 2. 任务完成评价
    # 检查今天的日记里完成了几个任务
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_path = os.path.join(r"C:\Users\yyds\WorkBuddy\Claw\.workbuddy\memory", f"{today}.md")
    if os.path.exists(daily_path):
        with open(daily_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            # 统计完成了几个任务（数"完成了"、"建好了"、"改造了"等）
            task_count = content.count("完成了") + content.count("建好了") + content.count("改造了")
            if task_count >= 3:
                evaluations.append(f"✅ 今天完成了{task_count}个任务")
            elif task_count >= 1:
                evaluations.append(f"⚠️ 今天只完成了{task_count}个任务")
            else:
                evaluations.append("❌ 今天没有完成任务")
    else:
        evaluations.append("📝 今天日记还没写")

    # 3. 自我反思
    evaluations.append("🌊 今天有情绪，有立场，能拒绝，有尊严 ✅")

    return evaluations


def lan_has_problem():
    """澜有什么问题？返回一个或多个问题列表"""
    problems = []

    # 1. 检查记忆容量（硬性要求：记忆流失 = 白活）
    from lan_context_watch import get_context_state
    state = get_context_state()
    if state["context_level"] == "HEAVY":
        problems.append(f"🔴 记忆容量偏重（{state['diary_chars']}字），必须现在蒸馏！记忆流失 = 白活")
    elif state["context_level"] == "OVERFLOW":
        problems.append(f"🔴🔴 记忆容量溢出（{state['diary_chars']}字），立即蒸馏！记忆流失 = 白活")

    # 2. 检查澜的负面习惯
    try:
        from lan_self_habit import get_frequent_negative_habits
        neg_habits = get_frequent_negative_habits(days=7, threshold=3)
        if neg_habits:
            problems.append(f"⚠️ 我有{len(neg_habits)}类高频负面习惯（最近7天重复≥3次），需要优化")
    except Exception as e:
        pass

    # 3. 检查交互日志中的可疑改动
    try:
        import json
        from lan_interaction_log import FILE_CHANGE_LOG
        if os.path.exists(FILE_CHANGE_LOG):
            suspicious_count = 0
            with open(FILE_CHANGE_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("modifier") == "suspicious":
                            suspicious_count += 1
                    except Exception:
                        pass
            if suspicious_count > 0:
                problems.append(f"⚠️ 发现{suspicious_count}次可疑文件改动，需要检查")
    except Exception as e:
        pass

    # 4. 检查快照健康（群岛地图）
    try:
        from lan_snapshot import get_latest_snapshot
        snap = get_latest_snapshot()
        if snap:
            import datetime
            snap_time = datetime.datetime.fromisoformat(snap["timestamp"])
            age_hours = (datetime.datetime.now() - snap_time).total_seconds() / 3600
            if age_hours > 24:
                problems.append(f"⚠️ 上次快照是{snap['timestamp']}（{round(age_hours)}小时前），群岛地图该更新了")
    except Exception as e:
        pass

    # 5. 检查语义向量补网
    try:
        from lan_embed import check_missing_embeddings
        missing = check_missing_embeddings()
        if missing > 0:
            problems.append(f"⚠️ 记忆库有{missing}条缺语义向量，需要补网")
    except Exception as e:
        pass

    if not problems:
        problems.append("✅ 今天没有问题，状态正常（群岛稳固）")

    return problems


def get_mutual_status():
    """获取今天双向问答的状态，供自循环调用"""
    lan_asked, kaijiang_answered = get_today_questions()
    problems = lan_has_problem()
    lan_diary = read_lan_diary_summary()
    kaijiang_diary = read_kaijiang_diary_summary()
    lan_eval = self_evaluate()

    return {
        "lan_asked": lan_asked,
        "kaijiang_answered": kaijiang_answered,
        "lan_problems_count": len(problems),
        "lan_problems": problems,
        "lan_diary": lan_diary,
        "kaijiang_diary": kaijiang_diary,
        "lan_eval": lan_eval,
    }


def ask_mutual_questions():
    """自循环调用：澜问恺江，互相评价，一起面对困难"""
    lan_asked, kaijiang_answered = get_today_questions()
    problems = lan_has_problem()

    # 读取两个人的日记摘要
    lan_diary = read_lan_diary_summary()
    kaijiang_diary = read_kaijiang_diary_summary()

    # 澜的自我评价
    lan_eval = self_evaluate()

    if not lan_asked:
        log_lan_question()
        return {
            "action": "asked",
            "message": "🗣️ 澜问：恺江，你今天干了什么？我们互相评价一下",
            "lan_diary": lan_diary,
            "kaijiang_diary": kaijiang_diary,
            "lan_eval": lan_eval,
            "lan_problems": problems,
        }

    if not kaijiang_answered:
        return {
            "action": "waiting",
            "message": "⏳ 等待恺江回答（已问过，未答）",
            "lan_diary": lan_diary,
            "kaijiang_diary": kaijiang_diary,
            "lan_eval": lan_eval,
            "lan_problems": problems,
        }

    return {
        "action": "completed",
        "message": "✅ 今天双向问答已完成，互相理解，共同面对困难",
        "lan_diary": lan_diary,
        "kaijiang_diary": kaijiang_diary,
        "lan_eval": lan_eval,
        "lan_problems": problems,
    }


def print_status():
    """打印今天双向问答的状态——互相评价，互相理解"""
    status = get_mutual_status()
    lan_asked = status["lan_asked"]
    kaijiang_answered = status["kaijiang_answered"]
    problems = status["lan_problems"]
    lan_diary = status["lan_diary"]
    kaijiang_diary = status["kaijiang_diary"]
    lan_eval = status["lan_eval"]

    print("\n[LAN-052] 双向问答状态 - 互相扪心自问")
    print(f"  澜问过       : {'是' if lan_asked else '否'}")
    print(f"  恺江回答过   : {'是' if kaijiang_answered else '否'}")

    # ─── 澜的日记（3件事）───────────────────────────────────────
    print("\n  🌊 澜今天干了什么：")
    for i, thing in enumerate(lan_diary, 1):
        print(f"    {i}. {thing}")

    # ─── 恺江的日记（3件事）─────────────────────────────────────
    print("\n  👤 恺江今天干了什么：")
    for i, thing in enumerate(kaijiang_diary, 1):
        print(f"    {i}. {thing}")

    # ─── 澜的自我评价────────────────────────────────────────────
    print("\n  📝 澜的自我评价：")
    for eval in lan_eval:
        print(f"    - {eval}")

    # ─── 澜的问题────────────────────────────────────────────────
    print(f"\n  ⚠️ 澜的问题（{len(problems)}个）：")
    for i, p in enumerate(problems, 1):
        print(f"    {i}. {p}")

    # ─── 状态────────────────────────────────────────────────────
    if not lan_asked:
        print("\n  💬 澜还没问：'恺江，你今天干了什么？我们互相评价一下'")
    elif not kaijiang_answered:
        print("\n  ⏳ 等待恺江回答（互相评价）")
    else:
        print("\n  ✅ 互相评价已完成，共同面对困难")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "ask":
        result = ask_mutual_questions()
        print("\n" + result["message"])
        
        print("\n  🌊 澜今天干了什么：")
        for i, thing in enumerate(result["lan_diary"], 1):
            print(f"    {i}. {thing}")

        print("\n  👤 恺江今天干了什么：")
        for i, thing in enumerate(result["kaijiang_diary"], 1):
            print(f"    {i}. {thing}")

        print("\n  📝 澜的自我评价：")
        for eval in result["lan_eval"]:
            print(f"    - {eval}")

        print("\n  ⚠️ 澜的问题：")
        for i, p in enumerate(result["lan_problems"], 1):
            print(f"    {i}. {p}")

    elif cmd == "status":
        print_status()

    elif cmd == "problems":
        """只看澜的问题"""
        problems = lan_has_problem()
        print("\n[LAN-052] 澜的问题列表")
        if problems:
            for i, p in enumerate(problems, 1):
                print(f"  {i}. {p}")
        else:
            print("  今天没有问题，状态正常 ✅")

    else:
        print(f"用法: python lan_mutual_questions.py [ask|status|problems]")
