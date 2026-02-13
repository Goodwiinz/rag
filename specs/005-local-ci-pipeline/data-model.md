# Data Model: Local CI Pipeline Runner

**Date**: 2026-02-12

## Overview

This feature has no persistent data model (no database tables, no API entities). All state is ephemeral within a single script execution.

## Runtime Data Structures

### Stage Result (bash associative array)

```bash
declare -A STAGE_RESULTS    # stage_name → exit_code (0=pass, 1+=fail, -1=skipped)
declare -A STAGE_DURATIONS  # stage_name → duration_seconds
declare -a STAGE_ORDER      # ordered list of stage names that were executed
```

### Prerequisite Flags (bash variables)

```bash
HAS_DOCKER=true/false
HAS_NODE=true/false
HAS_PYTHON=true/false
HAS_GIT=true/false
```

### Stage Registry (bash associative array)

```bash
declare -A STAGE_PREREQS  # stage_name → "docker"|"node"|"python"|"docker,python"
```

Maps each stage to its required tools, used to determine which stages can run.

## State Transitions

```
Stage Lifecycle:
  PENDING → RUNNING → PASSED (exit 0)
                    → FAILED (exit >0)
                    → SKIPPED (missing prereqs)
```

No persistent state between runs. Each invocation starts fresh.
