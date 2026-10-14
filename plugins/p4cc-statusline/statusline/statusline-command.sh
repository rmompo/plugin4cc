#!/usr/bin/env bash
input=$(cat)

# ANSI codes
RESET=$'\033[0m'
REV=$'\033[7m'
YELLOW=$'\033[33m'
CYAN=$'\033[36m'
PURPLE=$'\033[35m'
GREEN=$'\033[32m'
RED=$'\033[31m'

# Reverse-video block: set color first, then reverse → color becomes background
# Usage: rev_block "$COLOR" "$text"
rev_block() {
  printf '%s%s %s %s' "$1" "$REV" "$2" "$RESET"
}

# Pick color by percentage threshold
pct_color() {
  local rounded
  rounded=$(printf '%.0f' "$1")
  if   [ "$rounded" -le 40 ]; then printf '%s' "$GREEN"
  elif [ "$rounded" -le 75 ]; then printf '%s' "$YELLOW"
  else                              printf '%s' "$RED"
  fi
}


# Terminal width: $COLUMNS → /dev/tty → ancestor's tty → tput → 120
term_width() {
  local w pid tty
  if [ -n "${COLUMNS:-}" ]; then printf '%s' "$COLUMNS"; return; fi
  w=$(stty size </dev/tty 2>/dev/null | awk '{print $2}')
  if [ -z "$w" ]; then
    pid=$$
    while [ -n "$pid" ] && [ "$pid" -gt 1 ]; do
      tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
      if [ -n "$tty" ] && [ "$tty" != "?" ] && [ -e "/dev/$tty" ]; then
        w=$(stty size <"/dev/$tty" 2>/dev/null | awk '{print $2}')
        [ -n "$w" ] && break
      fi
      pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    done
  fi
  [ -z "$w" ] && w=$(tput cols 2>/dev/null)
  printf '%s' "${w:-120}"
}

# Shorten a path to fit $2 columns. Replaces directory levels with "…",
# from the highest level (closest to root) to the lowest; the last level is never replaced.
# Usage: fit_path "$path" "$max_len"
fit_path() {
  local path="$1" max="$2" prefix rest i k cand
  local -a parts
  case "$path" in
    "~"|"~/"*) prefix="~"; rest="${path#\~}" ;;
    *)         prefix="";  rest="$path" ;;
  esac
  rest="${rest#/}"
  IFS='/' read -r -a parts <<< "$rest"
  local n=${#parts[@]}
  for (( k=0; k<=n-1; k++ )); do
    cand="$prefix"
    for (( i=0; i<n; i++ )); do
      if [ "$i" -lt "$k" ]; then cand="${cand}/…"; else cand="${cand}/${parts[$i]}"; fi
    done
    [ "${#cand}" -le "$max" ] && { printf '%s' "$cand"; return; }
  done
  printf '%s' "$cand"   # most compressed form
}

project_dir=$(echo "$input" | jq -r '.workspace.project_dir // .workspace.current_dir' | sed "s|^$HOME|~|")
git_worktree=$(echo "$input" | jq -r '.workspace.git_worktree // .worktree.branch // empty')
if [ -z "$git_worktree" ]; then
  git_worktree=$(git -C "$(echo "$input" | jq -r '.workspace.project_dir // .workspace.current_dir')" branch --show-current 2>/dev/null || true)
fi
model=$(echo "$input" | jq -r '.model.display_name')
effort=$(echo "$input" | jq -r '.effort.level // empty')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
five_hour=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_day=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

SEP=" "

# Git branch — cyan reverse block
rest_out=""
plain_rest=""
if [ -n "$git_worktree" ]; then
  rest_out="${SEP}$(rev_block "$CYAN" "⎇ ${git_worktree}")"
  plain_rest="${SEP} ⎇ ${git_worktree} "
fi

# Model (+ effort level when the model supports it) — purple reverse block
model_label="✦ ${model}${effort:+ (${effort})}"
rest_out="${rest_out}${SEP}$(rev_block "$PURPLE" "$model_label")"
plain_rest="${plain_rest}${SEP} ${model_label} "

# Usage: CXxx% SNxx% WKxx% — uppercase labels, value colored by threshold
usage_part=""

if [ -n "$used_pct" ]; then
  c_val=$(printf '%.0f' "$used_pct")
  c_color=$(pct_color "$used_pct")
  usage_part="CX${c_color}${c_val}%${RESET}"
fi

if [ -n "$five_hour" ]; then
  s_val=$(printf '%.0f' "$five_hour")
  s_color=$(pct_color "$five_hour")
  s_str="SN${s_color}${s_val}%${RESET}"
  usage_part="${usage_part:+${usage_part} }${s_str}"
fi

if [ -n "$seven_day" ]; then
  w_val=$(printf '%.0f' "$seven_day")
  w_color=$(pct_color "$seven_day")
  w_str="WK${w_color}${w_val}%${RESET}"
  usage_part="${usage_part:+${usage_part} }${w_str}"
fi

if [ -n "$usage_part" ]; then
  rest_out="${rest_out}${SEP}${usage_part}"
  plain_usage=$(printf '%s' "$usage_part" | sed $'s/\033\\[[0-9;]*m//g')
  plain_rest="${plain_rest}${SEP}${plain_usage}"
fi

# Project dir — yellow reverse block; shrink path with "…" only if the line does not fit
width=$(term_width)
# Block is " ⌂ <path> " = path + 4 columns. Claude Code reserves ~4 columns on the
# right of the statusline (it truncates with "…" at width-4), so keep 5 of slack.
max_path=$(( width - ${#plain_rest} - 4 - 5 ))
project_dir=$(fit_path "$project_dir" "$max_path")
output="$(rev_block "$YELLOW" "⌂ ${project_dir}")${rest_out}"

echo -e "${output}"
