---
description: Commit all changes, push to remote, and open a pull request
---

Here is the current state of the repo:

```bash
git status
git diff --stat
git log --oneline -5
BRANCH=$(git branch --show-current)
echo "Current branch: $BRANCH"
echo "Base branch: develop"
```

Based on the changes above:

1. **Stage and commit**: Stage all relevant changed files (avoid .env, credentials, large binaries). Write a concise conventional commit message summarizing the changes. End with `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`.

2. **Push**: Push the current branch to origin with `-u` flag.

3. **Create PR**: Use `gh pr create` targeting `develop` with:
   - A short title (under 70 chars)
   - A body with `## Summary` (2-3 bullets) and `## Test plan` (checklist)
   - Footer: `Generated with [Claude Code](https://claude.com/claude-code)`

If the PR already exists, show the URL instead of creating a duplicate.
