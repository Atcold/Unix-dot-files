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

# Claude Code supplies both account quotas after its first API response.
# https://code.claude.com/docs/en/statusline#rate-limit-usage
# Render in memory so each Mac uses its own session data.
now_ts=$(date +%s)

build_usage() {
    local utilization=$1 reset_epoch=$2 window_seconds=$3 label=$4 show_reset=$5
    local elapsed_pct marker remaining projected filled bar i MARKER
    local USAGE_COLOR PACE_COLOR reset_display sec rounded reset_time
    # Elapsed share of the window (percent), and the bar cell boundary it falls on
    elapsed_pct=-1
    marker=-1
    if [ -n "$reset_epoch" ]; then
        remaining=$((reset_epoch - now_ts))
        [ $remaining -lt 0 ] && remaining=0
        [ "$remaining" -gt "$window_seconds" ] && remaining=$window_seconds
        elapsed_pct=$(( (window_seconds - remaining) * 100 / window_seconds ))
        marker=$(( (elapsed_pct * 10 + 50) / 100 ))
    fi

    # Usage colour gradient (for the percentage)
    if   [ "$utilization" -le 30 ]; then USAGE_COLOR=$'\033[38;5;34m'   # green
    elif [ "$utilization" -le 60 ]; then USAGE_COLOR=$'\033[38;5;178m'  # yellow
    elif [ "$utilization" -le 80 ]; then USAGE_COLOR=$'\033[38;5;166m'  # orange
    else                                  USAGE_COLOR=$'\033[38;5;160m'  # red
    fi

    # Pace colour (for the │ marker), using the existing 6-tier spectrum:
    # project current burn rate out to the reset and colour by where it lands.
    # The first tenth of either window or a finished window stays neutral.
    # The floor matters: utilization is a whole percent, so a 9-minute-old window
    # turns one prompt (1%) into 33 projected points and paints the marker red.
    if [ $elapsed_pct -ge 10 ] && [ $elapsed_pct -lt 100 ]; then
        projected=$((utilization * 100 / elapsed_pct))
        if   [ $projected -lt  50 ]; then PACE_COLOR=$'\033[38;5;34m'   # comfortable, green
        elif [ $projected -lt  75 ]; then PACE_COLOR=$'\033[38;5;37m'   # on track,    teal
        elif [ $projected -lt  90 ]; then PACE_COLOR=$'\033[38;5;178m'  # warming,     yellow
        elif [ $projected -lt 100 ]; then PACE_COLOR=$'\033[38;5;166m'  # pressing,    orange
        elif [ $projected -lt 120 ]; then PACE_COLOR=$'\033[38;5;160m'  # critical,    red
        else                              PACE_COLOR=$'\033[38;5;129m'  # runaway,     purple
        fi
    else
        PACE_COLOR=$'\033[38;5;255m'  # white
    fi

    # Progress bar (10 blocks) with │ marking our position in the window
    filled=$(( (utilization * 10 + 50) / 100 ))
    [ $filled -lt 0 ] && filled=0
    [ $filled -gt 10 ] && filled=10
    MARKER=$'\033[22m'"${PACE_COLOR}│"$'\033[2m'"${USAGE_COLOR}"
    bar=""
    i=0
    while [ $i -lt 10 ]; do
        [ $i -eq $marker ] && bar="${bar}${MARKER}"
        [ $i -lt $filled ] && bar="${bar}◼" || bar="${bar}◻"
        i=$((i+1))
    done
    [ $marker -ge 10 ] && bar="${bar}${MARKER}"

    # Reset time (24h), rounded to the nearest minute
    reset_display=""
    if [ "$show_reset" = yes ] || [ "$show_reset" = weekly ]; then
        sec=$((reset_epoch % 60))
        [ $sec -ge 30 ] && rounded=$((reset_epoch + 60 - sec)) || rounded=$((reset_epoch - sec))
        if [ "$show_reset" = weekly ]; then
            reset_time=$(LC_TIME=C date -r "$rounded" "+%a %-H:%M" 2>/dev/null)
        else
            reset_time=$(date -r "$rounded" "+%H:%M" 2>/dev/null)
        fi
        [ -n "$reset_time" ] && reset_display=" → ${reset_time}"
    fi

    printf '%s' $'\033[2m'"${USAGE_COLOR}${label}${utilization}% ${bar}${reset_display}"
}

USAGE_TEXT=""
WEEKLY_TEXT=""
for window in five_hour seven_day; do
    [ "$window" = five_hour ] && window_seconds=18000 || window_seconds=604800
    # Windows may be absent before the first response or after their reset.
    # The weekly window shows from 75% used, or earlier when consumption runs ahead of elapsed time.
    # Both checks use the unrounded figure.
    values=$(echo "$input" | jq -r --arg window "$window" --argjson now "$now_ts" --argjson duration "$window_seconds" '
        .rate_limits[$window]
        | select(type == "object")
        | select((.used_percentage | type) == "number" and (.resets_at | type) == "number")
        | select(.used_percentage >= 0 and .used_percentage <= 100 and .resets_at > $now)
        | [(.used_percentage | round), (.resets_at | floor),
           (.used_percentage >= 75 or .used_percentage * $duration > ($duration - ([.resets_at - $now, $duration] | min)) * 100)]
        | @tsv' 2>/dev/null)
    [ -z "$values" ] && continue
    IFS=$'\t' read -r utilization reset_epoch over_pace <<< "$values"
    if [ "$window" = five_hour ]; then
        USAGE_TEXT=$(build_usage "$utilization" "$reset_epoch" "$window_seconds" "" yes)
    elif [ "$over_pace" = true ]; then
        WEEKLY_TEXT=$(build_usage "$utilization" "$reset_epoch" "$window_seconds" "" weekly)
    fi
done

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
[ -n "$USAGE_TEXT" ] && LINE="${LINE} ${GRAY}·${RESET} ${USAGE_TEXT}${RESET}"
[ -n "$WEEKLY_TEXT" ] && LINE="${LINE} ${GRAY}·${RESET} ${WEEKLY_TEXT}${RESET}"

printf "%s\n" "$LINE"
