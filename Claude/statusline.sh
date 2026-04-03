#!/bin/bash
input=$(cat)

# Extract from JSON
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
MODEL=$(echo "$input" | jq -r '.model.display_name // "Claude"' | tr -d ' ')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)

# Show path from project root (e.g. .settings/Mac); fall back to basename of current dir
PROJECT_DIR=$(echo "$input" | jq -r '.workspace.project_dir // empty')
if [ -n "$PROJECT_DIR" ]; then
    REL="${DIR#$PROJECT_DIR}"
    SHORT_DIR="$(basename "$PROJECT_DIR")${REL}"
else
    SHORT_DIR=$(basename "$DIR")
fi

# Git branch + dirty indicator
GIT_INFO=""
if git -C "$DIR" rev-parse --git-dir &>/dev/null 2>&1; then
    BRANCH=$(git -C "$DIR" branch --show-current 2>/dev/null)
    DIRTY=$(git -C "$DIR" status --porcelain 2>/dev/null | head -1)
    [ -n "$DIRTY" ] && BRANCH="${BRANCH}*"
    [ -n "$BRANCH" ] && GIT_INFO=" ⎇ ${BRANCH}"
fi

# Computer name (macOS with Linux fallback)
COMPUTER=$(networksetup -getcomputername 2>/dev/null || hostname -s)

# --- Usage (5-hour session) ---
CACHE_FILE="$HOME/.claude/.statusline-usage-cache"
usage_result=""

# Try cache first (valid for 5 minutes)
if [ -f "$CACHE_FILE" ]; then
    cache_ts=$(grep "^TIMESTAMP=" "$CACHE_FILE" 2>/dev/null | cut -d= -f2)
    now_ts=$(date +%s)
    if [ -n "$cache_ts" ] && [ $((now_ts - cache_ts)) -lt 300 ]; then
        cache_util=$(grep "^UTILIZATION=" "$CACHE_FILE" | cut -d= -f2)
        cache_reset=$(grep "^RESETS_AT=" "$CACHE_FILE" | cut -d= -f2)
        [ -n "$cache_util" ] && usage_result="${cache_util}|${cache_reset}"
    fi
fi

# Fall back to Swift fetcher (managed by Claude Usage Tracker app)
if [ -z "$usage_result" ]; then
    swift_result=$(swift "$HOME/.claude/fetch-claude-usage.swift" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$swift_result" ]; then
        utilization=$(echo "$swift_result" | cut -d'|' -f1)
        resets_at=$(echo "$swift_result" | cut -d'|' -f2)
        if [ -n "$utilization" ] && [ "$utilization" != "ERROR"* ]; then
            usage_result="${utilization}|${resets_at}"
            { echo "TIMESTAMP=$(date +%s)"; echo "UTILIZATION=${utilization}"; echo "RESETS_AT=${resets_at}"; } > "$CACHE_FILE"
        fi
    fi
fi

# --- Build usage block ---
USAGE_TEXT=""
if [ -n "$usage_result" ]; then
    utilization=$(echo "$usage_result" | cut -d'|' -f1)
    resets_at=$(echo "$usage_result" | cut -d'|' -f2)

    # Progress bar (10 blocks)
    filled=$(( (utilization * 10 + 50) / 100 ))
    [ $filled -lt 0 ] && filled=0
    [ $filled -gt 10 ] && filled=10
    empty=$((10 - filled))
    bar=""
    i=0; while [ $i -lt $filled ]; do bar="${bar}▓"; i=$((i+1)); done
    i=0; while [ $i -lt $empty ]; do bar="${bar}░"; i=$((i+1)); done

    # Reset time (24h)
    reset_display=""
    if [ -n "$resets_at" ] && [ "$resets_at" != "null" ]; then
        iso_time=$(echo "$resets_at" | sed 's/\.[0-9]*Z$//')
        reset_epoch=$(date -ju -f "%Y-%m-%dT%H:%M:%S" "$iso_time" "+%s" 2>/dev/null)
        if [ -n "$reset_epoch" ]; then
            sec=$((reset_epoch % 60))
            [ $sec -ge 30 ] && reset_epoch=$((reset_epoch + 60 - sec)) || reset_epoch=$((reset_epoch - sec))
            reset_time=$(date -r "$reset_epoch" "+%H:%M" 2>/dev/null)
            [ -n "$reset_time" ] && reset_display=" → ${reset_time}"
        fi
    fi

    # Usage colour gradient
    if   [ "$utilization" -le 30 ]; then USAGE_COLOR=$'\033[38;5;34m'   # green
    elif [ "$utilization" -le 60 ]; then USAGE_COLOR=$'\033[38;5;178m'  # yellow
    elif [ "$utilization" -le 80 ]; then USAGE_COLOR=$'\033[38;5;166m'  # orange
    else                                  USAGE_COLOR=$'\033[38;5;160m'  # red
    fi

    USAGE_TEXT="${USAGE_COLOR}${utilization}% ${bar}${reset_display}"
fi

# --- Colours ---
MAGENTA=$'\033[1;35m'
WHITE=$'\033[38;5;255m'
BLUE=$'\033[1;34m'
YELLOW=$'\033[1;33m'
DIM=$'\033[2m'
GRAY=$'\033[0;90m'
RESET=$'\033[0m'

# --- Assemble ---
LINE="${MAGENTA}${MODEL}${WHITE}@${BLUE}${COMPUTER} ${YELLOW}${SHORT_DIR}${RESET}${GIT_INFO} ${DIM}${PCT}% ctx${RESET}"
[ -n "$USAGE_TEXT" ] && LINE="${LINE} ${GRAY}│${RESET} ${USAGE_TEXT}${RESET}"

printf "%s\n" "$LINE"
