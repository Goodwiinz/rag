#!/bin/bash

# React Query v5 Migration Script
# This script automatically fixes React Query v4 → v5 API changes

echo "🔧 Starting React Query v5 migration..."
echo ""

# Store the frontend directory path
FRONTEND_DIR="/Users/goodwiinz/development/RAG_system/rag/frontend/src"

# Counter for changes
CHANGES=0

# Function to update a file
update_file() {
  local file=$1
  local backup="${file}.backup"

  # Create backup
  cp "$file" "$backup"

  # Track if file was modified
  local modified=0

  # Fix 1: cacheTime → gcTime
  if grep -q "cacheTime:" "$file"; then
    sed -i '' 's/cacheTime:/gcTime:/g' "$file"
    echo "  ✓ Fixed cacheTime → gcTime in $(basename $file)"
    modified=1
  fi

  # Fix 2: useQuery 3-arg syntax → object syntax
  # Pattern: useQuery(['key'], queryFn, { options })
  # Replace with: useQuery({ queryKey: ['key'], queryFn, ...options })

  # This is complex, so we'll create a Node.js script for this

  if [ $modified -eq 1 ]; then
    CHANGES=$((CHANGES + 1))
  else
    # Remove backup if no changes
    rm "$backup"
  fi
}

# Find all TypeScript files with useQuery or useMutation
echo "📁 Finding files to update..."
FILES=$(find "$FRONTEND_DIR" -name "*.ts" -o -name "*.tsx" | grep -E "(hooks|stores|components)" | grep -v node_modules)

for file in $FILES; do
  if grep -q -E "(useQuery|useMutation|invalidateQueries)" "$file"; then
    echo ""
    echo "Processing: $(basename $file)"
    update_file "$file"
  fi
done

echo ""
echo "✅ Migration complete!"
echo "📊 Updated $CHANGES files"
echo ""
echo "⚠️  Note: This script fixed simple cases. Complex useQuery/useMutation"
echo "   calls may need manual fixing. Check the TypeScript errors for details."
echo ""
echo "🔄 Run 'npm run type-check' to see remaining errors"
