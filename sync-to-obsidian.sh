#!/bin/bash
# NOUS Memory → Obsidian Vault Sync Script
# Copies memory files from the project to your Obsidian claude-memory vault

VAULT="/Users/goodwiinz/Documents/claude-memory"
MEMORY="$(dirname "$0")/memory"

# Check vault exists
if [ ! -d "$VAULT" ]; then
  echo "❌ Obsidian vault not found at: $VAULT"
  echo "   Update the VAULT variable in this script if your vault is elsewhere."
  exit 1
fi

echo "📂 Syncing NOUS memory → Obsidian vault"
echo "   From: $MEMORY"
echo "   To:   $VAULT"
echo ""

# Create vault subdirectories
mkdir -p "$VAULT/people"
mkdir -p "$VAULT/projects"
mkdir -p "$VAULT/context"

# Sync files
copy_file() {
  local src="$1"
  local dest="$2"
  if [ -f "$src" ]; then
    cp "$src" "$dest"
    echo "  ✅ $(basename "$dest")"
  else
    echo "  ⚠️  Missing: $src"
  fi
}

copy_file "$MEMORY/glossary.md"              "$VAULT/glossary.md"
copy_file "$MEMORY/people/abdel.md"          "$VAULT/people/abdel.md"
copy_file "$MEMORY/projects/nous-platform.md" "$VAULT/projects/nous-platform.md"
copy_file "$MEMORY/projects/gap-analysis.md" "$VAULT/projects/gap-analysis.md"
copy_file "$MEMORY/context/tooling.md"       "$VAULT/context/tooling.md"

echo ""
echo "✅ Sync complete! Open Obsidian to see your notes."
