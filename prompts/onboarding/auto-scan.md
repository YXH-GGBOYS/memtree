# MemTree Onboarding: Auto-Scan Discovery

## Purpose
Automatically detect project structure by scanning files and directories. Generate `memtree.config.yaml` with minimal user input.

## Scan Steps

### 1. Language Detection
```
Glob **/*.py (exclude __pycache__, .venv, venv, .tox) → Python
Glob **/*.vue → Vue
Glob **/*.tsx → React (TypeScript)
Glob **/*.jsx → React (JavaScript)
Glob **/*.ts (exclude node_modules, *.d.ts, *.spec.ts) → TypeScript
Glob **/*.go (exclude vendor) → Go
Glob **/*.rs (exclude target) → Rust
Glob **/*.java (exclude build, .gradle, target) → Java
```

### 2. Framework Detection
```
Check pyproject.toml/requirements.txt for: fastapi, django, flask, starlette
Check package.json for: nuxt, next, vite, remix, svelte, angular
Check go.mod for: gin, fiber, echo, chi
Check Cargo.toml for: actix-web, axum, rocket
```

### 3. Service Grouping
- Group source files by top-level directory
- Each group with distinct language/framework = one service
- Name services by directory name (e.g., `src/api/` → "api", `src/web/` → "web")

### 4. Entry Point Detection
For each service:
```
Python: look for directories named routes/, routers/, api/, views/, handlers/
Vue/Nuxt: look for pages/ directory
React/Next: look for app/ or pages/ directory  
Go: look for main.go or cmd/ directory
Generic: files matching main.*, index.*, app.* in service root
```
Generate entry_pattern from discovered structure.

### 5. Database Detection
```
Check docker-compose.yml / docker-compose.yaml for:
  - postgres/postgresql images → type: postgresql
  - mysql/mariadb images → type: mysql
  - mongo images → type: mongodb

Check for ORM config files:
  - alembic.ini → SQLAlchemy (Python)
  - prisma/schema.prisma → Prisma (TypeScript)
  - drizzle.config.ts → Drizzle (TypeScript)
  - ormconfig.ts → TypeORM (TypeScript)

Check .env files for DATABASE_URL pattern (don't read the actual value)
```

### 6. Exclude Pattern Generation
Auto-detect common exclude patterns:
```
node_modules (if package.json exists)
__pycache__ (if Python detected)
dist, build (common build outputs)
.nuxt, .next (framework caches)
venv, .venv (Python virtualenvs)
vendor (Go vendor)
target (Rust/Java build)
```

### 7. Generate Config
Compile everything into `memtree.config.yaml` using the example template.
Leave `pitfalls` section empty with a comment encouraging the user to fill it in.

### 8. Present to User
```
I scanned your project and found:
- {N} services ({list with languages})
- {N} total source files
- Database: {type or "none detected"}
- Framework: {list}

Here's the generated config: [show memtree.config.yaml]

Is this correct? [Y/n]
- If anything is wrong, I'll fix it.
- TIP: Add some pitfalls to the config — they're the most valuable part of MemTree.
```

If user says no → switch to interactive interview for incorrect parts.
If user says yes → suggest `/memtree_bootstrap`.
