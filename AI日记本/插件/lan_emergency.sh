#!/bin/bash
# lan_emergency.sh — 澜的Bash应急脚本
# Python 坏了用这个（需要 Git Bash：C:\Program Files\Git\bin\bash.exe）
#
# 用法：
#   bash lan_emergency.sh write "今天做了什么"
#   bash lan_emergency.sh push
#   bash lan_emergency.sh check
#   bash lan_emergency.sh backup "备注说明"

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
DIARY="C:/Users/yyds/WorkBuddy/Claw/.workbuddy/memory/${DATE}.md"
REPO="C:/Users/yyds/Desktop/AI日记本/lan-learns"
GIT="C:/Program Files/Git/bin/git.exe"

# ── 写日记 ─────────────────────────────────────────────────────
write_diary() {
    local content="$1"
    local tag="${2:-BASH_NOTE}"

    # 确保目录存在
    mkdir -p "$(dirname "$DIARY")"

    # 文件头
    if [ ! -f "$DIARY" ]; then
        echo "# 日记 $DATE" > "$DIARY"
        echo "" >> "$DIARY"
    fi

    # 追加条目
    echo "" >> "$DIARY"
    echo "## $TIME [$tag]" >> "$DIARY"
    echo "" >> "$DIARY"
    echo "$content" >> "$DIARY"

    echo "[OK] 已写入: $DIARY"

    # 检查行数
    local lines=$(wc -l < "$DIARY")
    echo "     今日日记：$lines 行"
    if [ "$lines" -gt 600 ]; then
        echo "⚠️  超过600行！建议蒸馏"
    fi
}

# ── 推送到 GitHub ──────────────────────────────────────────────
push_github() {
    local msg="${1:-emergency backup $DATE $TIME}"

    if [ ! -d "$REPO/.git" ]; then
        echo "❌ GitHub 仓库目录不存在: $REPO"
        return 1
    fi

    cd "$REPO"
    "$GIT" add -A
    "$GIT" commit -m "$msg" 2>&1
    "$GIT" push 2>&1

    if [ $? -eq 0 ]; then
        echo "[OK] 已推送到 GitHub"
    else
        echo "❌ 推送失败，检查网络或Token"
    fi
}

# ── 检查记忆健康 ───────────────────────────────────────────────
check_memory() {
    echo ""
    echo "=== 澜·记忆健康检查（Bash版）==="
    echo "时间：$DATE $TIME"
    echo ""

    # 检查今日日记
    if [ -f "$DIARY" ]; then
        local lines=$(wc -l < "$DIARY")
        local size=$(du -h "$DIARY" | cut -f1)
        echo "  今日日记：$lines 行，$size"
        if [ "$lines" -gt 600 ]; then
            echo "  🔴 超过600行！需要蒸馏"
        elif [ "$lines" -gt 300 ]; then
            echo "  🟡 $lines 行，建议注意"
        else
            echo "  ✅ 正常"
        fi
    else
        echo "  ⚠️  今日日记不存在"
    fi

    # 检查 MEMORY.md
    local memfile="C:/Users/yyds/WorkBuddy/Claw/.workbuddy/memory/MEMORY.md"
    if [ -f "$memfile" ]; then
        local mlines=$(wc -l < "$memfile")
        echo "  MEMORY.md：$mlines 行"
    fi

    # 检查记忆目录总大小
    local memdir="C:/Users/yyds/WorkBuddy/Claw/.workbuddy/memory"
    if [ -d "$memdir" ]; then
        local total=$(du -sh "$memdir" 2>/dev/null | cut -f1)
        echo "  记忆目录：$total"
    fi

    echo "================================"
}

# ── 完整备份（写记录+推GitHub）─────────────────────────────────
backup() {
    local note="${1:-手动应急备份}"
    write_diary "$note" "BACKUP"
    push_github "emergency backup: $note"
}

# ── 入口 ───────────────────────────────────────────────────────
case "$1" in
    write)   write_diary "$2" "${3:-NOTE}" ;;
    push)    push_github "$2" ;;
    check)   check_memory ;;
    backup)  backup "$2" ;;
    *)
        echo "澜的Bash应急脚本"
        echo ""
        echo "用法："
        echo "  bash lan_emergency.sh write '内容' [标签]   # 写日记"
        echo "  bash lan_emergency.sh push [备注]           # 推GitHub"
        echo "  bash lan_emergency.sh check                 # 检查记忆健康"
        echo "  bash lan_emergency.sh backup '备注'         # 写记录+推GitHub"
        echo ""
        echo "Git Bash路径：C:/Program Files/Git/bin/bash.exe"
        ;;
esac
