"""Shared fixtures for the MemTree tests: temporary projects, fake transcripts, hook runners."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / "hooks"
SCRIPTS = REPO / "scripts"

DIGEST_FACTS = """# CRITICAL_FACTS

<!-- DIGEST-START -->
• Money is stored as integer cents in every service. See §2.
• Only billing writes the invoices table. See §2.
<!-- DIGEST-END -->

## 2. Data invariants
Details here.
"""


class TempCase(unittest.TestCase):
    """Each test gets a scratch dir; HOME points into it so nothing touches the real ~/.claude."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.state = self.tmp / "state"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def env(self, **extra: str) -> Dict[str, str]:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("MEMTREE_", "CLAUDE_"))}
        env.update({"HOME": str(self.home), "MEMTREE_STATE_DIR": str(self.state)})
        env.update(extra)
        return env

    def project(self, name: str = "app", facts: Optional[str] = DIGEST_FACTS) -> Path:
        root = self.tmp / name
        (root / ".memory").mkdir(parents=True)
        if facts is not None:
            (root / ".memory" / "CRITICAL_FACTS.md").write_text(facts, encoding="utf-8")
        return root

    def run_hook(self, hook: str, payload: Dict[str, object], **env: str) -> Tuple[int, str, bytes]:
        proc = subprocess.run([sys.executable, str(HOOKS / hook)], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, env=self.env(**env), timeout=30)
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stdout

    def run_script(self, script: str, args: Sequence[str], cwd: Path, **env: str) -> Tuple[int, str]:
        proc = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=str(cwd), capture_output=True,
                              text=True, env=self.env(**env), timeout=60)
        return proc.returncode, proc.stdout + proc.stderr


def assistant(mid: str, ctx: int, model: str = "claude-test-model", text: str = "ok",
              tool: Optional[Tuple[str, str, Dict[str, object]]] = None) -> Dict[str, object]:
    """One assistant transcript entry whose usage adds up to `ctx` context tokens."""
    content: List[Dict[str, object]] = [{"type": "text", "text": text}]
    if tool:
        content.append({"type": "tool_use", "id": tool[0], "name": tool[1], "input": tool[2]})
    return {"type": "assistant", "message": {"id": mid, "model": model, "content": content,
            "usage": {"input_tokens": 10, "cache_read_input_tokens": ctx - 110,
                      "cache_creation_input_tokens": 100, "output_tokens": 50}}}


def tool_result(tool_id: str, text: str) -> Dict[str, object]:
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text}]}}


def write_transcript(path: Path, entries: Sequence[Dict[str, object]], cwd: str = "/work/app") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "cwd": cwd, "message": {"role": "user", "content": "start"}}) + "\n")
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    return path
