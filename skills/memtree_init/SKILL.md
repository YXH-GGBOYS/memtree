# /memtree_init — Initialize MemTree for Your Project

## Usage
```
/memtree_init              # Interactive Q&A mode (recommended for first time)
/memtree_init --auto       # Auto-scan mode (fast, for standard project structures)
```

## What This Does
Generates a `memtree.config.yaml` file that describes your project structure, then prepares everything needed for `/memtree_bootstrap`.

## Mode A: Interactive Q&A (default)

Ask the user these questions in order. Skip any that aren't applicable.

### Phase 1: Project Overview
1. "What does your project do?" (1-2 sentences)
2. "What languages and frameworks do you use?" (e.g., Python FastAPI + Vue Nuxt + TypeScript)
3. "Is this a monorepo or multi-repo? How many services/modules?"

### Phase 2: Code Structure
For each service the user describes:
4. "Where is the code for {service}?" (directory path)
5. "What's the entry point pattern?" (e.g., routes/*.py, pages/**/*.vue)
6. Confirm by running: `ls {path}` to verify the directory exists

### Phase 3: Database (if applicable)
7. "Do you have a database? What type?" (PostgreSQL, MySQL, etc.)
8. "How do I run a SQL query?" (e.g., `docker exec db psql -U user -d mydb`)
9. "Which schemas should I analyze?" (e.g., public, auth, trading)

### Phase 4: Team Knowledge (most valuable part)
10. "What are the top 3 things a new developer gets wrong in your codebase?"
11. "Any naming inconsistencies? (e.g., DB column named X but code calls it Y)"
12. "Any money/currency gotchas? (different units in different places?)"
13. "Any transaction/concurrency rules? (who commits, who flushes?)"
14. "What was the last bug that took way too long to fix? What made it hard?"

### Phase 5: Generate Config
- Write `memtree.config.yaml` from answers
- Generate PATH_MAP (source prefix → .memory/ prefix)
- Show the user the config and ask for confirmation
- If confirmed, proceed to suggest `/memtree_bootstrap`

## Mode B: Auto-Scan (--auto)

1. Scan the project root:
   ```
   - Glob **/*.py → detect Python services
   - Glob **/*.vue → detect Vue frontend
   - Glob **/*.tsx → detect React frontend
   - Glob **/*.ts (not in node_modules) → detect TypeScript services
   - Glob **/*.go → detect Go services
   - Check docker-compose.yml / Dockerfile → detect database containers
   - Check package.json → detect framework (nuxt, next, vite, etc.)
   - Check pyproject.toml / requirements.txt → detect framework (fastapi, django, flask, etc.)
   ```

2. Group files into services by top-level directory

3. Detect entry points:
   - Python: `routes/`, `routers/`, `api/`, `views/` directories
   - Vue/Nuxt: `pages/` directory
   - React/Next: `app/` or `pages/` directory
   - Generic: files in root with `main`, `index`, `app` in name

4. Detect database:
   - Search for `docker-compose.yml` with postgres/mysql images
   - Search for `.env` files with DATABASE_URL (don't read values, just detect)
   - Search for `alembic.ini`, `prisma/schema.prisma`, `drizzle.config.ts`

5. Generate `memtree.config.yaml` with detected structure
6. Show to user: "I detected this structure. Correct? [Y/n]"
7. If user says no → fall back to interactive Q&A for the parts that are wrong

## After Init

Output:
```
memtree.config.yaml created.

Next step: run /memtree_bootstrap to build your .memory/ directory.
This will take ~30 min for a ~500 file project (scales linearly).
```

## Important
- Don't generate .memory/ files in this step — that's /memtree_bootstrap's job
- Don't read source code file contents during auto-scan — only scan file names, directory structure, and config files (package.json, pyproject.toml, docker-compose.yml, .env file names)
- The pitfalls section is optional but tell the user: "This is the most valuable part. AI agents will read this BEFORE writing any code in your project."
