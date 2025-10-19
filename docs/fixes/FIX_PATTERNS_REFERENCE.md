# Common Fix Patterns - Quick Reference

## Pattern 1: Divide-by-Zero Guards

### Before
```typescript
const average = total / count;
const percentage = (value / target) * 100;
```

### After
```typescript
const average = count > 0 ? total / count : 0;
const percentage = target === 0 ? 0 : ((value / target) * 100);
```

### Files Needing This
- AutomatedQualityChecks.tsx (average Score)
- QualityGovernanceCompliance.tsx (avgCompliance)
- QualityImprovementRecommendations.tsx (avgConfidence, percent calculation)
- ABTestingQueryImprovements.tsx (getMetricChange) ✅ FIXED

## Pattern 2: metadata.updated vs root updated

### Before
```typescript
setItems(items.map(item => 
  item.id === id 
    ? { ...item, ...updates, updated: new Date().toISOString() }
    : item
));
```

### After
```typescript
setItems(items.map(item => 
  item.id === id 
    ? { 
        ...item, 
        ...updates, 
        metadata: { 
          ...item.metadata, 
          ...updates.metadata,
          updated: new Date().toISOString() 
        }
      }
    : item
));
```

### Files Needing This
- AutomatedQualityChecks.tsx (2 places)
- PerformanceAlertingSystem.tsx (2 places)

## Pattern 3: parseInt with Radix

### Before
```typescript
const value = parseInt(e.target.value);
if (isNaN(value)) return;
```

### After
```typescript
const value = parseInt(e.target.value, 10);
if (Number.isNaN(value)) return;
// or with fallback
const value = parseInt(e.target.value, 10);
const safeValue = Number.isNaN(value) ? 0 : value;
```

### Files Needing This
- PerformanceAlertingSystem.tsx (3 places: duration, evaluationWindow, cooldownPeriod)

## Pattern 4: Replace All Underscores

### Before (Only replaces first)
```typescript
metric.replace('_', ' ')
```

### After (Replaces all)
```typescript
metric.replace(/_/g, ' ')
// or if replaceAll is supported
metric.replaceAll('_', ' ')
```

### Files Needing This
- ABTestingQueryImprovements.tsx ✅ FIXED

## Pattern 5: Adding Missing Icons

### Before
```typescript
import { Icon1, Icon2 } from 'lucide-react';
// ...later in code
<Icon3 className="h-4 w-4" />  // Error: Icon3 not defined
```

### After
```typescript
import { Icon1, Icon2, Icon3 } from 'lucide-react';
// ...later in code
<Icon3 className="h-4 w-4" />
```

### Files Needing This
- HumanEvaluationWorkflows.tsx (Shield, Globe, FileCheck)
- SecurityComplianceChecker.tsx (Target, ChevronRight)
- BenchmarkComparisonTools.tsx (Settings, ChevronRight)

## Pattern 6: Array Bounds Validation

### Before
```typescript
const day = daysOfWeek[schedule.dayOfWeek!];
```

### After
```typescript
const day = (schedule.dayOfWeek >= 0 && schedule.dayOfWeek <= 6) 
  ? daysOfWeek[schedule.dayOfWeek]
  : 'Invalid';
```

### Files Needing This
- AutomatedEvaluationScheduling.tsx (weekday lookup)

## Pattern 7: Export Interface

### Before
```typescript
interface MyConfig {
  field1: string;
  field2: number;
}

// Used in props
interface Props {
  onSave?: (config: MyConfig) => void;
}
```

### After
```typescript
export interface MyConfig {
  field1: string;
  field2: number;
}

// Used in props
interface Props {
  onSave?: (config: MyConfig) => void;
}
```

### Files Needing This
- DetailedAnalyticsReports.tsx (ReportConfig interface)

## Pattern 8: useEffect Cleanup

### Before
```typescript
useEffect(() => {
  setTimeout(() => {
    // do something
  }, 1000);
}, [deps]);
```

### After
```typescript
useEffect(() => {
  const timeoutId = setTimeout(() => {
    // do something
  }, 1000);
  
  return () => {
    clearTimeout(timeoutId);
  };
}, [deps]);
```

### Files Needing This
- DetailedAnalyticsReports.tsx

## Pattern 9: Dynamic vs Static Dates

### Before
```typescript
const test = {
  startDate: '2025-01-15T00:00:00Z',  // Static past date
  endDate: '2025-01-29T00:00:00Z'
};
```

### After
```typescript
const test = {
  startDate: new Date(Date.now() - 7*24*60*60*1000).toISOString(),  // 7 days ago
  endDate: new Date(Date.now() + 7*24*60*60*1000).toISOString()     // 7 days from now
};
```

### Files Needing This
- ABTestingQueryImprovements.tsx ✅ FIXED
- SecurityComplianceChecker.tsx (nextCheck, nextAssessment dates)

## Pattern 10: Type Safety for Any

### Before
```typescript
interface Props {
  onSave?: (data: any) => void;
}
```

### After
```typescript
interface SaveData {
  id: string;
  name: string;
  // ... other fields
}

interface Props {
  onSave?: (data: SaveData) => void;
}
```

### Files Needing This
- DetailedAnalyticsReports.tsx (onExportReport, onShareReport)
- AutomatedEvaluationScheduling.tsx (channels validation)

## Pattern 11: Deprecated String Methods

### Before
```typescript
str.substr(2, 9)  // Deprecated
```

### After
```typescript
str.substring(2, 11)  // Same behavior (start at 2, length 9)
// or
str.slice(2, 11)      // Same behavior (start at 2, end at 11)
```

### Files Fixed ✅
- ErrorBoundary.tsx
- errorTracking.ts
- loggingService.ts

## Pattern 12: String vs Number HTML Attributes

### Before
```typescript
<Input type="number" max={120} />  // JSX/TypeScript error
```

### After
```typescript
<Input type="number" max="120" />  // Correct
```

### Files Needing This
- HumanEvaluationWorkflows.tsx (multiple locations)

## Pattern 13: Security - Environment Variables

### Before
```yaml
username: "admin"
password: "password"
```

### After
```yaml
username: ${ENV_VAR_USERNAME}
password: ${ENV_VAR_PASSWORD}
# or
basic_auth_file: /path/to/secret  # chmod 600
```

### Files Fixed ✅
- monitoring/prometheus.yml

### Files Needing This
- docker-compose.yml (multiple credentials)

## Pattern 14: Security - Docker Login

### Before
```bash
docker login -u $USERNAME -p $PASSWORD  # Exposes in process list
```

### After
```bash
echo "$PASSWORD" | docker login --username $USERNAME --password-stdin
```

### Files Fixed ✅
- .github/workflows/ci-cd-pipeline.yml

## Pattern 15: Callback Invocation

### Before
```typescript
const handleUpdate = (item: Item) => {
  setItems(items.map(i => i.id === item.id ? item : i));
  // onItemUpdate callback never called!
};
```

### After
```typescript
const handleUpdate = useCallback((item: Item) => {
  const updatedItems = items.map(i => i.id === item.id ? item : i);
  setItems(updatedItems);
  onItemUpdate?.(item);  // Call parent callback
}, [items, onItemUpdate]);
```

### Files Needing This
- AutomatedEvaluationScheduling.tsx (onScheduleUpdate)
- CustomMetricCreationTracking.tsx (onMetricUpdate)
- PerformanceAlertingSystem.tsx (onAlertRuleUpdate)

## Quick Search Commands

Find files needing specific fixes:

```bash
# Find divide-by-zero candidates
grep -r "/ \w\+" --include="*.tsx" --include="*.ts"

# Find parseInt without radix
grep -r "parseInt([^,)]*)" --include="*.tsx" --include="*.ts"

# Find substr usage
grep -r "\.substr(" --include="*.tsx" --include="*.ts"

# Find replace('_', ' ') that should be replace(/_/g, ' ')
grep -r "replace('_', ' ')" --include="*.tsx" --include="*.ts"

# Find hardcoded credentials
grep -r 'password.*[:=].*["'\'']' --include="*.yml" --include="*.yaml"
```

## Testing After Fixes

```bash
# Frontend
cd frontend
npm run type-check    # TypeScript validation
npm run lint          # ESLint
npm run test:unit     # Unit tests
npm run build         # Production build

# Backend
cd backend
python -m pytest tests/
flake8 src/ tests/
black --check src/ tests/
mypy src/

# Security
npm audit
docker scan <image>
```
