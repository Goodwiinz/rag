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

launch   fetch REF, resolve SHA, create detached worktree, snapshot baseline,
         write session.env + AUDIT_HANDOFF.md under the session directory.
verify   re-hash worktree and diff vs baseline; assert HEAD == pinned SHA;
         report primary-checkout drift since launch (--strict-primary fails).
clean    verify, remove worktree, archive evidence under <base>/<repo>/archive/.
EOF
  exit 2
}

die() { printf 'launch_audit: %s\n' "$*" >&2; exit 1; }
need_dir() { [ -d "$1" ] || die "not a directory: $1"; }

write_env() { printf '%s=%q\n' "$1" "$2"; }

hash_tree() {
  local root="$1"
  local path digest target
  (
    cd "$root"
    while IFS= read -r -d '' path; do
      if [ -L "$path" ]; then
        target="$(readlink "$path")"
        printf 'L %q %q\n' "$path" "$target"
      elif [ -d "$path" ]; then
        printf 'D %q\n' "$path"
      else
        digest="$(shasum -a 256 "$path" | cut -d' ' -f1)"
        printf 'F %s %q\n' "$digest" "$path"
      fi
    done < <(find . \( -type d -o -type f -o -type l \) -print0 | LC_ALL=C sort -z)
  )
}

reject_external_symlinks() {
  local root="$1"
  local real_root link resolved
  real_root="$(realpath "$root")"
  while IFS= read -r -d '' link; do
    resolved="$(realpath "$link" 2>/dev/null)" || {
      printf 'broken symlink in audit worktree: %s\n' "$link" >&2
      return 1
    }
    case "$resolved" in
      "$real_root"|"$real_root"/*) ;;
      *)
        printf 'symlink escapes audit worktree: %s -> %s\n' "$link" "$resolved" >&2
        return 1
        ;;
    esac
  done < <(find "$root" -type l -print0)
}

primary_dirty_sha() {
  local repo="$1"
  local path full digest target
  {
    git -C "$repo" diff --no-ext-diff --binary HEAD --
    printf '\0'
    git -C "$repo" status --porcelain=v1 -z --untracked-files=all | LC_ALL=C sort -z
    printf '\0'
    while IFS= read -r -d '' path; do
      full="$repo/$path"
      if [ -L "$full" ]; then
        target="$(readlink "$full")"
        printf 'L %q %q\n' "$path" "$target"
      elif [ -f "$full" ]; then
        digest="$(shasum -a 256 "$full" | cut -d' ' -f1)"
        printf 'F %s %q\n' "$digest" "$path"
      fi
    done < <(git -C "$repo" ls-files --others --exclude-standard -z | LC_ALL=C sort -z)
  } | shasum -a 256 | cut -d' ' -f1
}

primary_dirty_count() {
  git -C "$1" status --porcelain=v1 --untracked-files=all | wc -l | tr -d ' '
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
    [[ "$SLUG" =~ ^[A-Za-z0-9._-]+$ ]] || die "slug must use only letters, numbers, '.', '_', or '-'"
    need_dir "$REPO"
    REPO="$(cd "$REPO" && pwd)"
    mkdir -p "$BASE"
    BASE="$(cd "$BASE" && pwd)"

    git -C "$REPO" fetch origin "$REF" >/dev/null 2>&1 || die "fetch failed: origin/$REF"
    SHA="$(git -C "$REPO" rev-parse 'FETCH_HEAD^{commit}')" || die "resolve failed"

    SESSION_ID="${SLUG}-$(date +%Y%m%d-%H%M%S)-$$"
    SESSION_DIR="$BASE/${REPO##*/}/$SESSION_ID"
    mkdir -p "$SESSION_DIR"

    PRIMARY_HEAD="$(git -C "$REPO" rev-parse HEAD)"
    PRIMARY_BRANCH="$(git -C "$REPO" branch --show-current)"
    PRIMARY_DIRTY_SHA="$(primary_dirty_sha "$REPO")"
    PRIMARY_DIRTY_COUNT="$(primary_dirty_count "$REPO")"
    git -c core.hooksPath=/dev/null -C "$REPO" worktree add --detach "$SESSION_DIR/worktree" "$SHA" >/dev/null \
      || die "worktree add failed"

    WT="$SESSION_DIR/worktree"
    WT_STATUS="$(git -C "$WT" status --porcelain=v1 --untracked-files=all --ignored)"
    if [ -n "$WT_STATUS" ] || ! reject_external_symlinks "$WT"; then
      git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true
      rmdir "$SESSION_DIR" 2>/dev/null || true
      die "audit worktree is not an isolated copy of $SHA"
    fi
    hash_tree "$WT" > "$SESSION_DIR/worktree.baseline.manifest"

    {
      write_env AUDIT_SESSION_ID "$SESSION_ID"
      write_env AUDIT_REPO "$REPO"
      write_env AUDIT_REF "origin/$REF"
      write_env AUDIT_SHA "$SHA"
      write_env AUDIT_WORKTREE "$WT"
      write_env AUDIT_BASELINE "$SESSION_DIR/worktree.baseline.manifest"
      write_env AUDIT_LAUNCHED_AT "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      write_env AUDIT_HOST "$(hostname)"
      write_env AUDIT_TOOL_SHA "$(shasum -a 256 "$0" | cut -d' ' -f1)"
      write_env AUDIT_PRIMARY_HEAD "$PRIMARY_HEAD"
      write_env AUDIT_PRIMARY_BRANCH "$PRIMARY_BRANCH"
      write_env AUDIT_PRIMARY_DIRTY_SHA "$PRIMARY_DIRTY_SHA"
      write_env AUDIT_PRIMARY_DIRTY_COUNT "$PRIMARY_DIRTY_COUNT"
    } > "$SESSION_DIR/session.env"
    chmod 400 "$SESSION_DIR/session.env"

    {
      printf '# Audit handoff — %s\n\n' "$SLUG"
      printf '%s\n' "- target SHA: \`$SHA\`"
      printf '%s\n' "- ref: \`origin/$REF\`"
      printf '%s\n' "- checkout (read-only): \`$WT\`"
      printf '%s\n' "- session id: \`$SESSION_ID\`"
      printf '\n## Prior ledgers (historical context — re-verify at this SHA)\n\n'
      repo_base="${REPO##*/}"
      repo_base_lc="$(printf '%s' "$repo_base" | tr '[:upper:]' '[:lower:]')"
      ledgers_dir=""
      for cand in "$HOME/.audit-ledgers/$repo_base_lc" "$HOME/.audit-ledgers/$repo_base"; do
        if [ -d "$cand" ] && ls "$cand"/*.md >/dev/null 2>&1; then ledgers_dir="$cand"; break; fi
      done
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
- Prior ledger status is not evidence for this SHA; re-verify applicable findings.
- Zero findings is a valid outcome. Never inflate to hit a quota.
RULES
    } > "$SESSION_DIR/AUDIT_HANDOFF.md"

    echo "session:     $SESSION_ID"
    echo "sha:         $SHA"
    echo "worktree:    $WT"
    echo "handoff:     $SESSION_DIR/AUDIT_HANDOFF.md"
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
    PRIMARY_DRIFT=0
    RECEIPT="$SESSION_DIR/verify.receipt"
    rm -f "$RECEIPT"

    TOOL_SHA_NOW="$(shasum -a 256 "$0" | cut -d' ' -f1)"
    if [ "$TOOL_SHA_NOW" != "$AUDIT_TOOL_SHA" ]; then
      echo "FAIL: launcher changed since audit launch: $AUDIT_TOOL_SHA -> $TOOL_SHA_NOW"
      RC=1
    else
      echo "OK: launcher unchanged ($TOOL_SHA_NOW)"
    fi

    hash_tree "$AUDIT_WORKTREE" > "$SESSION_DIR/worktree.final.manifest"
    if ! cmp -s "$SESSION_DIR/worktree.baseline.manifest" "$SESSION_DIR/worktree.final.manifest"; then
      echo "FAIL: worktree mutated during audit:"
      diff -u "$SESSION_DIR/worktree.baseline.manifest" "$SESSION_DIR/worktree.final.manifest" || true
      RC=1
    else
      echo "OK: worktree byte-identical to baseline ($(wc -l < "$SESSION_DIR/worktree.baseline.manifest" | tr -d ' ') files)"
    fi

    WT_STATUS="$(git -C "$AUDIT_WORKTREE" status --porcelain=v1 --untracked-files=all --ignored)"
    if [ -n "$WT_STATUS" ]; then
      echo "FAIL: worktree differs from pinned commit:"
      printf '%s\n' "$WT_STATUS"
      RC=1
    else
      echo "OK: worktree Git state clean"
    fi

    HEAD_NOW="$(git -C "$AUDIT_WORKTREE" rev-parse HEAD)"
    if [ "$HEAD_NOW" != "$AUDIT_SHA" ]; then
      echo "FAIL: worktree HEAD moved: $AUDIT_SHA -> $HEAD_NOW"
      RC=1
    else
      echo "OK: HEAD still pinned at $AUDIT_SHA"
    fi

    NOW_HEAD="$(git -C "$AUDIT_REPO" rev-parse HEAD)"
    if [ "$AUDIT_PRIMARY_HEAD" != "$NOW_HEAD" ]; then
      msg="primary HEAD moved during audit window: $AUDIT_PRIMARY_HEAD -> $NOW_HEAD"
      PRIMARY_DRIFT=1
      if [ "$STRICT_PRIMARY" -eq 1 ]; then echo "FAIL: $msg"; RC=1; else echo "WARN: $msg"; fi
    else
      echo "OK: primary HEAD unchanged ($NOW_HEAD)"
    fi

    NOW_BRANCH="$(git -C "$AUDIT_REPO" branch --show-current)"
    NOW_DIRTY_SHA="$(primary_dirty_sha "$AUDIT_REPO")"
    NOW_DIRTY_COUNT="$(primary_dirty_count "$AUDIT_REPO")"
    if [ "$AUDIT_PRIMARY_BRANCH" != "$NOW_BRANCH" ] || \
       [ "$AUDIT_PRIMARY_DIRTY_SHA" != "$NOW_DIRTY_SHA" ]; then
      msg="primary working state changed (branch $AUDIT_PRIMARY_BRANCH -> $NOW_BRANCH; dirty files $AUDIT_PRIMARY_DIRTY_COUNT -> $NOW_DIRTY_COUNT)"
      PRIMARY_DRIFT=1
      if [ "$STRICT_PRIMARY" -eq 1 ]; then echo "FAIL: $msg"; RC=1; else echo "WARN: $msg (other sessions may own these)"; fi
    else
      echo "OK: primary branch and working state unchanged"
    fi

    if [ "$RC" -eq 0 ]; then
      {
        printf 'status=ok\n'
        printf 'session=%s\n' "$AUDIT_SESSION_ID"
        printf 'sha=%s\n' "$AUDIT_SHA"
        printf 'verified_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf 'manifest_sha=%s\n' "$(shasum -a 256 "$SESSION_DIR/worktree.final.manifest" | cut -d' ' -f1)"
        if [ "$PRIMARY_DRIFT" -eq 0 ]; then printf 'primary=unchanged\n'; else printf 'primary=changed\n'; fi
        printf 'strict_primary=%s\n' "$STRICT_PRIMARY"
      } > "$RECEIPT"
      chmod 400 "$RECEIPT"
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
    "$0" verify --session "$SESSION_DIR"
    # shellcheck disable=SC1090
    source "$SESSION_DIR/session.env"
    grep -qx 'status=ok' "$SESSION_DIR/verify.receipt" || die "successful verification receipt missing"
    grep -qx "sha=$AUDIT_SHA" "$SESSION_DIR/verify.receipt" || die "verification receipt SHA mismatch"
    git -C "$AUDIT_REPO" worktree remove --force "$AUDIT_WORKTREE" \
      || die "worktree remove failed"
    ARCHIVE="$(dirname "$SESSION_DIR")/archive"
    mkdir -p "$ARCHIVE"
    mv "$SESSION_DIR/worktree.baseline.manifest" "$ARCHIVE/$AUDIT_SESSION_ID.worktree.baseline.manifest"
    mv "$SESSION_DIR/worktree.final.manifest" "$ARCHIVE/$AUDIT_SESSION_ID.worktree.final.manifest"
    mv "$SESSION_DIR/verify.receipt" "$ARCHIVE/$AUDIT_SESSION_ID.verify.receipt"
    mv "$SESSION_DIR/AUDIT_HANDOFF.md" "$ARCHIVE/$AUDIT_SESSION_ID.AUDIT_HANDOFF.md"
    mv "$SESSION_DIR/session.env" "$ARCHIVE/$AUDIT_SESSION_ID.session.env"
    rmdir "$SESSION_DIR" || die "session directory contains unarchived evidence: $SESSION_DIR"
    echo "cleaned: worktree removed, manifests archived under $ARCHIVE"
    ;;

  *)
    usage
    ;;
esac
