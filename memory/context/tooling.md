# Tooling & Workflow Context

## Connected Services

| Service | Purpose | Status |
|---------|---------|--------|
| **Linear** | Issue tracking (Goodwiinz team) | Connected via MCP |
| **GitHub** | Source control (goodwiins/rag) | Available via `gh` CLI |
| **Slack** | Team communication | Connected via MCP |
| **Gmail** | Email (allocs16@gmail.com) | Connected via MCP |
| **Google Drive** | Document storage | Connected via MCP |
| **Supabase** | Database hosting | Connected via MCP |
| **Vercel** | Frontend deployment | Connected via MCP |
| **Obsidian** | Knowledge vault (claude-memory) | Synced via git hook + sync script |

## Obsidian Vault

- **Path:** `/Users/goodwiinz/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude-memory`
- **MCP server:** `obsidian-mcp` (npx package)
- **Config location:** `/Users/goodwiinz/.claude/projects/-Users-goodwiinz-development-RAG-system/.mcp.json`
- **Sync method:** `sync-to-obsidian.sh` script + git post-commit hook (auto-syncs `memory/` changes)
- **Status:** Active — iCloud synced, auto-sync via git hook

## Scheduled Tasks

| Task | Schedule | What it does |
|------|----------|-------------|
| `nous-daily-sync` | Weekdays 9:10 AM | GitHub activity + Linear issues + memory updates + Obsidian vault sync |

## Branch Strategy

- Feature branches from `develop`
- PRs target `develop`
- Repo: github.com/goodwiins/rag

## Local Paths

| What | Path |
|------|------|
| Project root | `/Users/goodwiinz/development/RAG_system` |
| Claude project config | `/Users/goodwiinz/.claude/projects/-Users-goodwiinz-development-RAG-system/` |
| Obsidian vault | `/Users/goodwiinz/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude-memory` |
| Scheduled tasks | `/Users/goodwiinz/Documents/Claude/Scheduled/` |
