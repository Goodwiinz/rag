#!/bin/bash

# MUI Grid v7 Migration Script
# Migrates from <Grid item xs={12}> to <Grid size={{ xs: 12 }}>

echo "🔄 Starting MUI Grid v7 migration..."

# Find all files with Grid components
FILES=(
  "src/components/analytics/AnalyticsChartsMUI.tsx"
  "src/components/analytics/AnalyticsDashboardMUI.tsx"
  "src/components/analytics/PerformanceMonitoringMUI.tsx"
  "src/components/analytics/QualityMetricsDashboardMUI.tsx"
  "src/components/analytics/RecommendationsEngineMUI.tsx"
  "src/components/analytics/UserBehaviorAnalyticsMUI.tsx"
  "src/components/analytics/AnalyticsRouterMUI.tsx"
)

# Create backups
echo "📦 Creating backups..."
for file in "${FILES[@]}"; do
  if [ -f "$file" ]; then
    cp "$file" "$file.backup"
    echo "  ✓ Backed up $file"
  fi
done

echo ""
echo "🔧 Applying migrations..."

# Migration patterns for Grid v7
# Pattern 1: <Grid item xs={value}> → <Grid size={{ xs: value }}>
# Pattern 2: <Grid item xs={v1} md={v2}> → <Grid size={{ xs: v1, md: v2 }}>
# Pattern 3: <Grid item xs={v1} md={v2} lg={v3}> → <Grid size={{ xs: v1, md: v2, lg: v3 }}>

for file in "${FILES[@]}"; do
  if [ -f "$file" ]; then
    echo "  Processing $file..."

    # Use Node.js for complex regex replacements
    node -e "
const fs = require('fs');
const content = fs.readFileSync('$file', 'utf8');

let updated = content;

// Pattern: <Grid item xs={12} md={6} lg={4}>
updated = updated.replace(
  /<Grid\\s+item\\s+xs=\\{(\\d+)\\}\\s+md=\\{(\\d+)\\}\\s+lg=\\{(\\d+)\\}/g,
  '<Grid size={{ xs: \$1, md: \$2, lg: \$3 }}'
);

// Pattern: <Grid item xs={12} md={6}>
updated = updated.replace(
  /<Grid\\s+item\\s+xs=\\{(\\d+)\\}\\s+md=\\{(\\d+)\\}/g,
  '<Grid size={{ xs: \$1, md: \$2 }}'
);

// Pattern: <Grid item xs={12} sm={6}>
updated = updated.replace(
  /<Grid\\s+item\\s+xs=\\{(\\d+)\\}\\s+sm=\\{(\\d+)\\}/g,
  '<Grid size={{ xs: \$1, sm: \$2 }}'
);

// Pattern: <Grid item xs={12}>
updated = updated.replace(
  /<Grid\\s+item\\s+xs=\\{(\\d+)\\}/g,
  '<Grid size={{ xs: \$1 }}'
);

// Pattern: <Grid item md={6}>
updated = updated.replace(
  /<Grid\\s+item\\s+md=\\{(\\d+)\\}/g,
  '<Grid size={{ md: \$1 }}'
);

// Pattern: <Grid item> (no size specified - remove item prop)
updated = updated.replace(
  /<Grid\\s+item>/g,
  '<Grid>'
);

fs.writeFileSync('$file', updated, 'utf8');
console.log('    ✓ Updated $file');
"
  fi
done

echo ""
echo "✅ Migration complete!"
echo ""
echo "📊 Running type-check to verify..."
npm run type-check 2>&1 | grep -E "error TS|Found [0-9]+ error" | tail -5

echo ""
echo "💡 To restore backups if needed:"
echo "   for f in src/components/analytics/*MUI.tsx.backup; do mv \"\$f\" \"\${f%.backup}\"; done"
