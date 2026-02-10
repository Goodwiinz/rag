#!/bin/bash
# PostToolUse hook: auto-format files after Write|Edit
# Reads tool_input.file_path from stdin JSON

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

case "$FILE_PATH" in
  *.ts|*.tsx|*.js|*.jsx|*.css|*.md)
    cd "$CLAUDE_PROJECT_DIR/frontend" && npx prettier --write "$FILE_PATH" 2>/dev/null || true
    ;;
esac

exit 0
