#!/bin/bash
input=$(cat)

# Extract from JSON
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)

# Abbreviate home dir
SHORT_DIR="${DIR/#$HOME/~}"

# Git branch + dirty indicator
GIT_INFO=""
if git -C "$DIR" rev-parse --git-dir &>/dev/null 2>&1; then
    BRANCH=$(git -C "$DIR" branch --no-color 2>/dev/null | sed -e '/^[^*]/d' -e 's/* //')
    DIRTY=$(git -C "$DIR" status --porcelain 2>/dev/null | head -1)
    [ -n "$DIRTY" ] && BRANCH="${BRANCH}*"
    GIT_INFO=" [$BRANCH]"
fi

# Computer name (macOS with Linux fallback)
COMPUTER=$(networksetup -getcomputername 2>/dev/null || hostname -s)

# ANSI colours matching bash PS1
MAGENTA='\033[1;35m'
WHITE='\033[38;5;255m'
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
DIM='\033[2m'
RESET='\033[0m'

printf "${MAGENTA}${USER}${WHITE}@${BLUE}${COMPUTER} ${YELLOW}${SHORT_DIR}${RESET}${GIT_INFO} ${DIM}${PCT}% ctx${RESET}\n"
