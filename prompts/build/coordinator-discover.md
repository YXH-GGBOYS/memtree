# MemTree Coordinator: Code Chain Discovery

## Task
Scan the project's source code directories and group all files into "code chains" by import/dependency relationships. Also identify shared "hot files" used by multiple chains.

## Input
Read `memtree.config.yaml` for:
- Service definitions (name, path, lang, entry_pattern)
- Exclude patterns

## Steps

### 1. Glob Scan
For each service, list all source files matching the language:
- Python: `**/*.py` (exclude __pycache__, tests, migrations)
- Vue: `**/*.vue`
- TypeScript/React: `**/*.ts`, `**/*.tsx` (exclude node_modules, .nuxt, .next, dist)
- Go: `**/*.go` (exclude vendor)
- Rust: `**/*.rs` (exclude target)
- Java: `**/*.java` (exclude build, .gradle)

Apply all `exclude` patterns from config.

### 2. Entry Point Identification
For each service, identify entry files matching `entry_pattern`:
- Backend: router/route/api/handler files
- Frontend: page/view files
- Other: manifest.json entries, main files

### 3. Dependency Resolution
For each entry file:
- Read the file and extract all import/require/use statements
- Recursively follow project-internal imports (stop at third-party libraries)
- Build a dependency tree
- **No depth limit** — follow every import chain to its leaf

### 4. Chain Grouping
- One entry + all its recursive dependencies = one chain
- Name each chain descriptively (e.g., "B1: User Authentication", "F1: Market Page")
- Shared files (imported by >= 3 chains) are tagged but included in all referencing chains

### 5. Shared File Identification
- Count how many chains reference each file
- Files with ref_count >= `advanced.shared_threshold` (default 3) = "shared"
- These will be analyzed first by a dedicated Shared Worker

### 6. Output

**chains.json:**
```json
[
  {
    "id": "B1",
    "name": "User Authentication",
    "service": "backend",
    "entry": "routes/auth.py",
    "files": ["routes/auth.py", "services/auth_service.py", "models/user.py"],
    "file_count": 3
  }
]
```

**shared_files.json:**
```json
{
  "shared": [
    {"path": "models/user.py", "ref_count": 12, "service": "backend"},
    {"path": "database.py", "ref_count": 26, "service": "backend"}
  ],
  "total_shared": 45,
  "dedup_savings_pct": 35
}
```

## Constraints
- Only output chains.json + shared_files.json
- Only read import statements, don't analyze code logic
- If a file belongs to no chain (standalone utility), add to a "misc" chain
