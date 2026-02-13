#!/usr/bin/env bash
# scripts/ci/utils.sh — Shared utilities for local CI pipeline runner
# Colors, formatting, timing, and prerequisite checks

# ─── Color Constants ───────────────────────────────────────────────────────────
# Respects NO_COLOR (https://no-color.org/) and CI environment variable
if [[ -z "${NO_COLOR:-}" && -z "${CI:-}" && -t 1 ]]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    RESET='\033[0m'
else
    GREEN=''
    RED=''
    YELLOW=''
    CYAN=''
    BOLD=''
    DIM=''
    RESET=''
fi

# ─── Formatting ───────────────────────────────────────────────────────────────

print_header() {
    local title="$1"
    echo ""
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${CYAN}  ${title}${RESET}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}"
}

print_separator() {
    echo -e "${DIM}──────────────────────────────────────────${RESET}"
}

print_stage_header() {
    local stage_name="$1"
    echo ""
    echo -e "${BOLD}▶ ${stage_name}${RESET}"
    print_separator
}

# ─── Timing ───────────────────────────────────────────────────────────────────

format_duration() {
    local seconds="$1"
    if (( seconds >= 60 )); then
        local minutes=$(( seconds / 60 ))
        local remaining=$(( seconds % 60 ))
        printf "%dm %02ds" "$minutes" "$remaining"
    else
        printf "%ds" "$seconds"
    fi
}

# ─── Prerequisite Checks ─────────────────────────────────────────────────────

HAS_DOCKER=false
HAS_NODE=false
HAS_PYTHON=false
HAS_GIT=false

check_prereqs() {
    echo -e "${BOLD}Checking prerequisites...${RESET}"

    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        HAS_DOCKER=true
        echo -e "  ${GREEN}✓${RESET} docker + docker compose"
    else
        echo -e "  ${YELLOW}⚠${RESET} docker/docker compose not found — Docker stages will be skipped"
    fi

    if command -v node &>/dev/null && command -v npm &>/dev/null; then
        HAS_NODE=true
        echo -e "  ${GREEN}✓${RESET} node $(node --version) + npm"
    else
        echo -e "  ${YELLOW}⚠${RESET} node/npm not found — frontend stages will be skipped"
    fi

    if command -v python3 &>/dev/null && command -v pip3 &>/dev/null || command -v pip &>/dev/null; then
        HAS_PYTHON=true
        echo -e "  ${GREEN}✓${RESET} python3 $(python3 --version 2>&1 | awk '{print $2}')"
    else
        echo -e "  ${YELLOW}⚠${RESET} python3/pip not found — backend test stages will be skipped"
    fi

    if command -v git &>/dev/null; then
        HAS_GIT=true
        echo -e "  ${GREEN}✓${RESET} git"
    else
        echo -e "  ${YELLOW}⚠${RESET} git not found — --auto mode unavailable"
    fi

    echo ""
}

# ─── Prerequisite Validation ──────────────────────────────────────────────────

check_stage_prereqs() {
    local prereqs="$1"
    local IFS=','
    for prereq in $prereqs; do
        case "$prereq" in
            docker)  [[ "$HAS_DOCKER" == "true" ]] || return 1 ;;
            node)    [[ "$HAS_NODE" == "true" ]]   || return 1 ;;
            python)  [[ "$HAS_PYTHON" == "true" ]] || return 1 ;;
            git)     [[ "$HAS_GIT" == "true" ]]    || return 1 ;;
        esac
    done
    return 0
}
