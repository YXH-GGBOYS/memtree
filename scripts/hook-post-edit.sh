#!/bin/bash
# MemTree PostToolUse hook -- triggers incremental update scheduling after Write/Edit.
# Reads hook data (JSON) from stdin, extracts file_path, passes to trigger-incremental.py.
#
# Claude Code PostToolUse hook stdin contains: {tool_name, tool_input, tool_output, ...}
#
# Installation:
#   Add to your Claude Code settings.json hooks:
#   {
#     "hooks": {
#       "PostToolUse": [
#         { "command": "bash /path/to/memtree/scripts/hook-post-edit.sh" }
#       ]
#     }
#   }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRIGGER="$SCRIPT_DIR/trigger-incremental.py"

# Check that trigger script exists
if [ ! -f "$TRIGGER" ]; then
    exit 0
fi

# Extract tool_name and file_path from stdin JSON (cat handles multi-line input)
HOOK_INPUT=$(cat)
TOOL_NAME=$(echo "$HOOK_INPUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    print(data.get('tool_name', ''))
except Exception:
    print('')
" 2>/dev/null)

# Only trigger for write operations
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi

FILE_PATH=$(echo "$HOOK_INPUT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    # PostToolUse hook stdin: {tool_name, tool_input, tool_output, ...}
    inp = data.get('tool_input', data)
    if isinstance(inp, str):
        inp = json.loads(inp)
    print(inp.get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null)

if [ -n "$FILE_PATH" ]; then
    python3 "$TRIGGER" "$FILE_PATH" >> "${SCRIPT_DIR}/../.memory/.hook-log" 2>&1 &
fi
