# Code Style Conventions

## Python (Backend)

### Formatting
- Black: line-length 88, target Python 3.12
- isort: profile "black"
- mypy: strict mode

### Naming
- snake_case for functions/variables
- PascalCase for classes
- UPPER_CASE for constants

### Logging
- structlog: `logger = structlog.get_logger(__name__)`

### Imports
1. Standard library
2. Third-party
3. Local (from src.*)

## TypeScript (Frontend)

### Formatting
- Prettier: semi, single quotes, trailing comma es5, width 80, tab 2
- ESLint with React hooks + TypeScript recommended

### Naming
- camelCase for functions/variables (CLAUDE.md says camelCase files too)
- PascalCase for components/types

### Path Aliases
- @/* → ./src/* or ./app/*

### Package Manager
- pnpm (NOT npm) — only pnpm-lock.yaml committed

## General
- No hardcoded hex colors — use CSS vars / Tailwind theme classes
- IconButton requires aria-label
- Don't name query params same as imported modules (e.g. status shadows fastapi.status)
- PostCSS uses 'tailwindcss' plugin, NOT '@tailwindcss/postcss' (v3)
