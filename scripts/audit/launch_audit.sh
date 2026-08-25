#!/usr/bin/env bash
# audit-isolation launcher: read-only audits run in a detached worktree pinned
# to a fetched SHA; zero-mutation is asserted against byte-level baselines.
set -euo pipefail

usage() {
  cat <<'EOF'
usage:
  launch_audit.sh launch --repo DIR --ref REF --slug SLUG [--base DIR]
  launch_audit.sh verify --session DIR [--strict-primary]
  launch_audit.sh clean  --session DIR

launch   fetch REF, resolve SHA, create detached worktree, snapshot baseline
         hashes of every worktree file, write session.env + AUDIT_HANDOFF.md.
verify   re-hash worktree and diff vs baseline; assert HEAD == pinned SHA;
         report primary-checkout drift since launch (--strict-primary fails).
clean    remove worktree, archive manifests under <base>/archive/.
EOF
  exit 2
}

die() { printf 'launch_audit: %s\n' "$*" >&2; exit 1; }
need_dir() { [ -d "$1" ] || die "not a directory: $1"; }

hash_tree() {
  local root="$1"
  (cd "$root" && find . -type f \
      ! -path './.git/*' \
      ! -path './AUDIT_HANDOFF.md' \
      ! -name 'session.env' \
      ! -name '*.baseline.manifest' \
      -print0 | sort -z | xargs -0 shasum -a 256)
}

primary_snapshot() {
  local repo="$1"
  printf 'head=%s\nbranch=%s\ndirty_sha=%s\ndirty_count=%s\n' \
    "$(git -C "$repo" rev-parse HEAD)" \
    "$(git -C "$repo" branch --show-current)" \
    "$(git -C "$repo" status --porcelain=v1 | sort | shasum -a 256 | cut -d' ' -f1)" \
    "$(git -C "$repo" status --porcelain=v1 | wc -l | tr -d ' ')"
}

cmd="${1:-}"; shift || true
[ -n "$cmd" ] || usage

case "$cmd" in
  launch)
    REPO=""; REF=""; SLUG=""; BASE="$HOME/.audit-worktrees"
    while [ $# -gt 0 ]; do
      case "$1" in
        --repo) REPO="$2"; shift 2;;
        --ref)  REF="$2"; shift 2;;
        --slug) SLUG="$2"; shift 2;;
        --base) BASE="$2"; shift 2;;
        *) die "unknown flag: $1";;
      esac
    done
    [ -n "$REPO" ] && [ -n "$REF" ] && [ -n "$SLUG" ] || usage
    need_dir "$REPO"
    REPO="$(cd "$REPO" && pwd)"

    git -C "$REPO" fetch origin "$REF" >/dev/null 2>&1 || die "fetch failed: origin/$REF"
    SHA="$(git -C "$REPO" rev-parse FETCH_HEAD)" || die "resolve failed"

    SESSION_ID="${SLUG}-$(date +%Y%m%d-%H%M%S)-$$"
    SESSION_DIR="$BASE/${REPO##*/}/$SESSION_ID"
    mkdir -p "$SESSION_DIR"

    PRIMARY_BEFORE="$(primary_snapshot "$REPO")"
    git -C "$REPO" worktree add --detach "$SESSION_DIR/worktree" "$SHA" >/dev/null \
      || die "worktree add failed"

    WT="$SESSION_DIR/worktree"
    hash_tree "$WT" > "$SESSION_DIR/worktree.baseline.manifest"

    {
      printf 'AUDIT_SESSION_ID=%s\n'  "$SESSION_ID"
      printf 'AUDIT_REPO=%s\n'       "$REPO"
      printf 'AUDIT_REF=origin/%s\n' "$REF"
      printf 'AUDIT_SHA=%s\n'        "$SHA"
      printf 'AUDIT_WORKTREE=%s\n'   "$WT"
      printf 'AUDIT_BASELINE=%s\n'   "$SESSION_DIR/worktree.baseline.manifest"
      printf 'AUDIT_LAUNCHED_AT=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf 'AUDIT_HOST=%s\n'       "$(hostname)"
      printf 'AUDIT_TOOL_SHA=%s\n'   "$(shasum -a 256 "$0" | cut -d' ' -f1)"
      printf '%s\n' "$PRIMARY_BEFORE" | sed 's/^/AUDIT_PRIMARY_/'
    } > "$SESSION_DIR/session.env"
    chmod 400 "$SESSION_DIR/session.env"

    {
      printf '# Audit handoff — %s\n\n' "$SLUG"
      printf '%s\n' "- target SHA: \`$SHA\`"
      printf '%s\n' "- ref: \`origin/$REF\`"
      printf '%s\n' "- checkout (read-only): \`$WT\`"
      printf '%s\n' "- session id: \`$SESSION_ID\`"
      printf '\n## Prior ledgers (context only — do not re-derive findings)\n\n'
      repo_base="${REPO##*/}"
      repo_base_lc="$(printf '%s' "$repo_base" | tr '[:upper:]' '[:lower:]')"
      ledgers_dir=""
      for cand in "$HOME/.audit-ledgers/$repo_base_lc" "$HOME/.audit-ledgers/$repo_base"; do
        if [ -d "$cand" ] && ls "$cand"/*.md >/dev/null 2>&1; then ledgers_dir="$cand"; break; fi
      done
      if [ -z "$ledgers_dir" ]; then
        for d in "$HOME"/.audit-ledgers/*/; do
          [ -d "$d" ] || continue
          if ls "${d}"*.md >/dev/null 2>&1; then ledgers_dir="${d%/}"; break; fi
        done
      fi
      if [ -n "$ledgers_dir" ]; then
        for f in "$ledgers_dir"/*.md; do
          [ -e "$f" ] || continue
          title="$(head -n 1 "$f" | sed 's/^# //')"
          printf '%s\n' "- $f — $title"
        done
      else
        printf '%s\n' "- (none)"
      fi
      cat <<'RULES'

## Isolation rules
- This checkout is READ-ONLY evidence at the pinned SHA. Do not commit, stash,
  checkout, reset, or install anything into it.
- The primary working copy is OFF-LIMITS for the entire audit.
- Every finding must cite `file:line` inside this worktree plus the SHA above.
- Zero findings is a valid outcome. Never inflate to hit a quota.
RULES
    } > "$WT/AUDIT_HANDOFF.md"

    echo "session:     $SESSION_ID"
    echo "sha:         $SHA"
    echo "worktree:    $WT"
    echo "handoff:     $WT/AUDIT_HANDOFF.md"
    echo "baseline:    $(wc -l < "$SESSION_DIR/worktree.baseline.manifest" | tr -d ' ') files hashed"
    ;;

  verify)
    SESSION_DIR=""; STRICT_PRIMARY=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --session) SESSION_DIR="$2"; shift 2;;
        --strict-primary) STRICT_PRIMARY=1; shift;;
        *) die "unknown flag: $1";;
      esac
    done
    [ -n "$SESSION_DIR" ] || usage
    need_dir "$SESSION_DIR"
    # shellcheck disable=SC1090
    source "$SESSION_DIR/session.env"
    RC=0

    hash_tree "$AUDIT_WORKTREE" > "$SESSION_DIR/worktree.final.manifest"
    MUTATED="$(diff "$SESSION_DIR/worktree.baseline.manifest" "$SESSION_DIR/worktree.final.manifest" | grep -E '^[<>]' | awk '{print $3}' | sort -u || true)"
    if [ -n "$MUTATED" ]; then
      echo "FAIL: worktree mutated during audit:"
      printf '  %s\n' $MUTATED
      RC=1
    else
      echo "OK: worktree byte-identical to baseline ($(wc -l < "$SESSION_DIR/worktree.baseline.manifest" | tr -d ' ') files)"
    fi

    HEAD_NOW="$(git -C "$AUDIT_WORKTREE" rev-parse HEAD)"
    if [ "$HEAD_NOW" != "$AUDIT_SHA" ]; then
      echo "FAIL: worktree HEAD moved: $AUDIT_SHA -> $HEAD_NOW"
      RC=1
    else
      echo "OK: HEAD still pinned at $AUDIT_SHA"
    fi

    REPO_BASE="${AUDIT_REPO##*/}"
    PRIMARY_NOW="$(primary_snapshot "$AUDIT_REPO")"
    BEFORE_DIRTY="$(sed -n 's/^AUDIT_PRIMARY_//p' "$SESSION_DIR/session.env")"
    BEFORE_HEAD="$(printf '%s\n' "$BEFORE_DIRTY" | sed -n 's/^head=//p')"
    NOW_HEAD="$(printf '%s\n' "$PRIMARY_NOW" | sed -n 's/^head=//p')"
    if [ "$BEFORE_HEAD" != "$NOW_HEAD" ]; then
      msg="primary HEAD moved during audit window: $BEFORE_HEAD -> $NOW_HEAD"
      if [ "$STRICT_PRIMARY" -eq 1 ]; then echo "FAIL: $msg"; RC=1; else echo "WARN: $msg"; fi
    else
      echo "OK: primary HEAD unchanged ($NOW_HEAD)"
    fi
    BEFORE_COUNT="$(printf '%s\n' "$BEFORE_DIRTY" | sed -n 's/^dirty_count=//p')"
    NOW_COUNT="$(printf '%s\n' "$PRIMARY_NOW" | sed -n 's/^dirty_count=//p')"
    if [ "$BEFORE_COUNT" != "$NOW_COUNT" ]; then
      msg="primary dirty-file count changed: $BEFORE_COUNT -> $NOW_COUNT"
      if [ "$STRICT_PRIMARY" -eq 1 ]; then echo "FAIL: $msg"; RC=1; else echo "WARN: $msg (other sessions may own these)"; fi
    else
      echo "OK: primary dirty-state size unchanged"
    fi
    exit "$RC"
    ;;

  clean)
    SESSION_DIR=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --session) SESSION_DIR="$2"; shift 2;;
        *) die "unknown flag: $1";;
      esac
    done
    [ -n "$SESSION_DIR" ] || usage
    need_dir "$SESSION_DIR"
    # shellcheck disable=SC1090
    source "$SESSION_DIR/session.env"
    git -C "$AUDIT_REPO" worktree remove --force "$AUDIT_WORKTREE" \
      || die "worktree remove failed"
    ARCHIVE="$(dirname "$SESSION_DIR")/archive"
    mkdir -p "$ARCHIVE"
    mv "$SESSION_DIR/worktree.baseline.manifest" "$SESSION_DIR/worktree.final.manifest" "$ARCHIVE/" 2>/dev/null || true
    mv "$SESSION_DIR/session.env" "$ARCHIVE/$AUDIT_SESSION_ID.session.env" 2>/dev/null || true
    rmdir "$SESSION_DIR" 2>/dev/null || true
    echo "cleaned: worktree removed, manifests archived under $ARCHIVE"
    ;;

  *)
    usage
    ;;
esac
