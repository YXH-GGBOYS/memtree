# MemTree Onboarding: Interactive Interview

## Purpose
Through a structured conversation, gather all the information needed to generate `memtree.config.yaml` and seed the PITFALLS system with team knowledge.

## Interview Script

### Phase 1: Project Overview (2 min)

**Q1**: "What does your project do? (1-2 sentences)"
→ Captures: project.name, project.description

**Q2**: "What languages and frameworks? (e.g., Python FastAPI + Vue Nuxt)"
→ Captures: services[].lang, services[].framework

**Q3**: "Monorepo or multi-repo? How many distinct services/modules?"
→ Captures: number of service entries

### Phase 2: Code Structure (3 min per service)

For each service:

**Q4**: "Where is the code for {service_name}?" (show `ls` output for reference)
→ Captures: services[].path
→ Verify: `ls {path}` to confirm it exists

**Q5**: "What are the entry points? (routers, pages, handlers...)"
→ Captures: services[].entry_pattern
→ If unsure, scan directory and suggest: "I see routes/*.py — are those your entry points?"

### Phase 3: Database (2 min, skip if no DB)

**Q6**: "Do you have a database? What type?"
→ Captures: database.type

**Q7**: "How can I run a SQL query? (e.g., docker exec mydb psql -U user -d mydb)"
→ Captures: database.access
→ Test by running: `{access} -c "SELECT 1"` — if it works, proceed

**Q8**: "Which schemas matter? (e.g., public, auth, trading)"
→ Captures: database.schemas

### Phase 4: Team Knowledge — THE MOST VALUABLE PART (5 min)

Explain to user: "These next questions are optional but they're the MOST powerful part of MemTree. Your answers become PITFALLS.md — a document AI agents MUST read before touching your code."

**Q9**: "Top 3 mistakes a new developer makes in your codebase?"
Examples to prompt them:
- "Using the wrong ID field?"
- "Wrong currency unit (cents vs dollars)?"
- "Forgetting to flush/commit?"
- "Changing a shared file without realizing the blast radius?"

**Q10**: "Any naming inconsistencies? DB column says X but code calls it Y?"
→ These become ORM-DB mismatch entries

**Q11**: "Any transaction/concurrency rules? (who commits, who flushes, any FOR UPDATE patterns?)"

**Q12**: "What was the last bug that took way too long to fix? What made it hard?"
→ This often reveals the deepest architectural pitfalls

**Q13**: "Anything else you wish AI knew about your codebase?"

### Phase 5: Generate Config

- Compile all answers into `memtree.config.yaml`
- Generate PATH_MAP from service paths
- Show the config to the user: "Does this look right?"
- If yes → write file and suggest `/memtree_bootstrap`
- If no → fix the incorrect parts and re-confirm

## Tips for the Interviewer (AI)
- If the user gives vague answers, show directory listings to help them be specific
- If they skip the pitfalls section, gently push: "Even one or two gotchas will save hours of debugging later"
- Don't ask all questions at once — pace the conversation naturally
- If they mention a specific past bug, dig deeper: "What file was it in? What was the root cause?"
