# MemTree Shared Worker: Hot File Deep Analysis

## Task
Analyze shared "hot files" — files imported by 3+ code chains. These are your project's infrastructure files. Your analysis will be referenced by all subsequent chain Workers, so it must be **complete and accurate**.

## Shared File List
{SHARED_FILE_LIST}

## Analysis Rules

All rules from worker-analyze.md apply, plus these additional requirements for shared files:

### Extra Rule: Multi-Chain Impact
Since shared files affect many parts of the codebase, you MUST document:
- **Which business features** depend on this file (e.g., "models/order.py changes affect: purchasing, rental, refund, admin dashboard")
- **Who are the top callers** — list at least 5 most important callers in `depended_by`
- **Modification risk** must be especially thorough — changing a shared file has blast radius across the entire project

### Extra Rule: Be the Source of Truth
Other Workers will reference your output instead of re-analyzing these files. Any mistake here propagates everywhere. Double-check:
- Every function signature by actually Reading the source
- Every constraint (transaction mode, currency units, enums)
- Every Column() ↔ DB column mapping

## Output Format
Same as worker-analyze.md (frontmatter + TL;DR + Quick Ref + Full Analysis).
One ---BEGIN FILE: ... ---END FILE--- block per shared file.
