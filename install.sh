#!/usr/bin/env bash
# MemTree manual install, for people who do not use Claude Code plugins.
#
#   ./install.sh            copy skills, hooks, scripts and templates; print the hook JSON to merge
#   ./install.sh --apply    same, then merge the hooks into settings.json (after backing it up)
#
# Where things go (CLAUDE_HOME defaults to ~/.claude):
#   $CLAUDE_HOME/skills/memtree-{init,handoff,closeout,lookup}/SKILL.md
#   $CLAUDE_HOME/memtree/{hooks,scripts,templates}/
# settings.json is never touched without --apply. The hooks only inject text, never block or reroute
# tool calls, and print nothing in projects without a MemTree .memory/ folder.
set -euo pipefail

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "install.sh: unknown option: $arg" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "install.sh: python3 (3.9+) is required" >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "install.sh: python3 is older than 3.9" >&2; exit 1; }

SRC="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
DEST="$CLAUDE_HOME/memtree"

mkdir -p "$DEST" "$CLAUDE_HOME/skills"
for part in hooks scripts templates; do
  rm -rf "${DEST:?}/$part"
  cp -R "$SRC/$part" "$DEST/$part"
done
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Skills reference ${CLAUDE_PLUGIN_ROOT}; outside the plugin system that becomes $DEST.
for skill in "$SRC"/skills/memtree-*/; do
  name="$(basename "$skill")"
  mkdir -p "$CLAUDE_HOME/skills/$name"
  python3 - "$skill/SKILL.md" "$CLAUDE_HOME/skills/$name/SKILL.md" "$DEST" <<'PY'
import sys
src, dst, root = sys.argv[1:4]
text = open(src, encoding="utf-8").read().replace("${CLAUDE_PLUGIN_ROOT}", root)
open(dst, "w", encoding="utf-8").write(text)
PY
  echo "skill:   $CLAUDE_HOME/skills/$name/SKILL.md"
done
echo "files:   $DEST/{hooks,scripts,templates}"

HOOKS_JSON="$(python3 - "$DEST" <<'PY'
import json, sys
root = sys.argv[1]
cmd = lambda name: {"type": "command", "command": f'python3 "{root}/hooks/{name}"', "timeout": 10}
print(json.dumps({"hooks": {
    "UserPromptSubmit": [{"hooks": [cmd("facts_digest.py"), cmd("ctx_handoff_reminder.py")]}],
    "SessionStart": [{"matcher": "compact", "hooks": [cmd("post_compact.py")]}],
}}, indent=2))
PY
)"

if [[ "$APPLY" -eq 0 ]]; then
  echo
  echo "Merge this into $CLAUDE_HOME/settings.json (or rerun with --apply to do it for you):"
  echo "$HOOKS_JSON"
  exit 0
fi

SETTINGS="$CLAUDE_HOME/settings.json"
if [[ -f "$SETTINGS" ]]; then
  BACKUP="$SETTINGS.memtree-backup-$(date +%Y%m%d-%H%M%S)"
  cp -p "$SETTINGS" "$BACKUP"
  echo "backup:  $BACKUP"
fi
python3 - "$SETTINGS" "$HOOKS_JSON" <<'PY'
import json, os, sys
path, new = sys.argv[1], json.loads(sys.argv[2])["hooks"]
settings = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fh:
        settings = json.load(fh)  # stop on invalid JSON rather than overwrite it
hooks = settings.setdefault("hooks", {})
existing = {h.get("command") for groups in hooks.values() for g in groups for h in g.get("hooks", [])}
added = 0
for event, groups in new.items():
    for group in groups:
        fresh = [h for h in group["hooks"] if h["command"] not in existing]
        if fresh:
            hooks.setdefault(event, []).append(dict(group, hooks=fresh))
            added += len(fresh)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(settings, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
print(f"settings: {path} ({added} hook command(s) added, {sum(len(g['hooks']) for v in new.values() for g in v) - added} already present)")
PY
echo "Restart Claude Code (or open /hooks) for the hooks to load."
