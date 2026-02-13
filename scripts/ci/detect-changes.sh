#!/usr/bin/env bash
# scripts/ci/detect-changes.sh — Git diff-based change detection for --auto mode

detect_changed_stages() {
    local changed_files
    changed_files=$(git diff --name-only develop...HEAD 2>/dev/null || git diff --name-only main...HEAD 2>/dev/null || echo "")

    if [[ -z "$changed_files" ]]; then
        echo -e "${YELLOW}⚠ Could not detect changes (no commits ahead of develop/main)${RESET}"
        echo -e "  Running all stages as fallback"
        echo "ALL"
        return
    fi

    local backend_changed=false
    local frontend_changed=false
    local docker_changed=false
    local ci_changed=false

    while IFS= read -r file; do
        case "$file" in
            backend/*|tests/*)              backend_changed=true ;;
            frontend/*)                     frontend_changed=true ;;
            *Dockerfile*|docker-compose*)   docker_changed=true ;;
            .github/*)                      ci_changed=true ;;
        esac
    done <<< "$changed_files"

    # If CI config or Docker infrastructure changed → run all stages
    if [[ "$ci_changed" == "true" || "$docker_changed" == "true" ]]; then
        echo -e "  Detected CI/Docker changes — running all stages"
        echo "ALL"
        return
    fi

    # Build stage list based on what changed
    local stages=()

    if [[ "$backend_changed" == "true" ]]; then
        echo -e "  Detected backend changes"
        stages+=(lint-backend unit-tests security-scan resilience-tests)
    fi

    if [[ "$frontend_changed" == "true" ]]; then
        echo -e "  Detected frontend changes"
        stages+=(lint-frontend frontend-tests)
    fi

    # If both changed, add integration stages but not e2e
    if [[ "$backend_changed" == "true" && "$frontend_changed" == "true" ]]; then
        stages+=(integration-tests api-contract-tests)
    fi

    if [[ ${#stages[@]} -eq 0 ]]; then
        echo -e "  No relevant code changes detected — running all stages as fallback"
        echo "ALL"
        return
    fi

    # Return space-separated stage names
    echo "${stages[*]}"
}
