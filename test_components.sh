#!/bin/bash
find frontend/src/components -name "*.tsx" | while read file; do
    if grep -q '<Button' "$file" && grep -q 'size="icon"' "$file" && ! grep -q 'aria-label' "$file"; then
        echo "$file"
    fi
done
