# Code Style and Conventions

## Python (Backend)

### Formatting
- **Black**: line-length 88, target Python 3.11
- **isort**: profile "black", multi_line_output 3

### Type Hints
- **mypy**: strict mode enabled
  - `disallow_untyped_defs = true`
  - `warn_return_any = true`
- All functions should have type annotations

### Docstrings
- Use triple-quoted docstrings for functions and classes
- Example from codebase:
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      """Application lifespan events"""
  ```

### Naming Conventions
- snake_case for functions and variables
- PascalCase for classes
- UPPER_CASE for constants

### Import Order
1. Standard library
2. Third-party packages
3. Local imports (from src.*)

### Logging
- Use structlog for structured logging
- Logger per module: `logger = structlog.get_logger(__name__)`

### Error Handling
- Use try/except with specific exceptions
- Log errors with context
- Continue gracefully when possible

## TypeScript (Frontend)

### Formatting (Prettier)
- Semi: true
- Single quotes
- Trailing comma: es5
- Print width: 80
- Tab width: 2

### ESLint Rules
- React hooks rules enabled
- TypeScript recommended rules
- Unused vars with `_` prefix allowed

### Path Aliases
- `@/*` → `./src/*` or `./app/*`
- `@/components/*` → `./src/components/*`
- `@/lib/*` → `./src/lib/*`

### Component Structure
- Functional components with TypeScript
- Radix UI primitives with shadcn/ui styling
- Zustand for state management
- TanStack Query for server state

### Naming Conventions
- camelCase for functions and variables
- PascalCase for components and types
- kebab-case for file names
