#!/bin/bash
find frontend/src/components -name "*.tsx" | while read file; do
    if grep -q '<Button' "$file" && ! grep -q 'aria-label' "$file"; then
        if grep -A 2 '<Button' "$file" | grep -q '<[A-Z][a-zA-Z]*Icon\|<[A-Z][a-zA-Z]* className'; then
            echo "$file"
        fi
    fi
done
