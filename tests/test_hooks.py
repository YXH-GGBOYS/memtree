"""Hook behaviour, exercised the way Claude Code runs them: a subprocess with JSON on stdin."""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import DIGEST_FACTS, HOOKS, TempCase, assistant, write_transcript  # noqa: E402

sys.path.insert(0, str(HOOKS))
import memtree_common as mc  # noqa: E402

BUDGET = 9000


class FactsDigestTest(TempCase):
    def test_injects_once_then_pointer(self) -> None:
        root = self.project()
        payload = {"session_id": "sess-1", "cwd": str(root)}
        code, out, _ = self.run_hook("facts_digest.py", payload)
        self.assertEqual(code, 0)
        self.assertIn("• Money is stored as integer cents", out)
        self.assertIn("• Only billing writes", out)
        self.assertTrue((self.state / "digest" / "sess-1").is_file())

        code, out, _ = self.run_hook("facts_digest.py", payload)
        self.assertEqual(code, 0)
        self.assertNotIn("• Money", out)
        self.assertIn("injected earlier in this session", out)
        self.assertEqual(out.count("\n"), 1)

    def test_reinjects_when_digest_changes(self) -> None:
        root = self.project()
        payload = {"session_id": "sess-2", "cwd": str(root)}
        self.run_hook("facts_digest.py", payload)
        facts = root / ".memory" / "CRITICAL_FACTS.md"
        facts.write_text(DIGEST_FACTS.replace("integer cents", "integer minor units"), encoding="utf-8")
        _, out, _ = self.run_hook("facts_digest.py", payload)
        self.assertIn("integer minor units", out)
        self.assertIn("changed since it was last injected", out)
        _, out, _ = self.run_hook("facts_digest.py", payload)
        self.assertNotIn("integer minor units", out)

    def test_editing_outside_digest_does_not_reinject(self) -> None:
        root = self.project()
        payload = {"session_id": "sess-3", "cwd": str(root)}
        self.run_hook("facts_digest.py", payload)
        facts = root / ".memory" / "CRITICAL_FACTS.md"
        facts.write_text(DIGEST_FACTS + "\n## 3. More detail\n", encoding="utf-8")
        _, out, _ = self.run_hook("facts_digest.py", payload)
        self.assertNotIn("• Money", out)

    def test_silent_without_memory_dir(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        code, out, raw = self.run_hook("facts_digest.py", {"session_id": "s", "cwd": str(plain)})
        self.assertEqual((code, raw), (0, b""))
        # a bare .memory/ from some other tool is not a MemTree project either
        (plain / ".memory").mkdir()
        code, out, raw = self.run_hook("facts_digest.py", {"session_id": "s", "cwd": str(plain)})
        self.assertEqual((code, raw), (0, b""))
        self.assertFalse(self.state.exists())

    def test_no_session_id_injects_every_time(self) -> None:
        root = self.project()
        for _ in range(2):
            code, out, _ = self.run_hook("facts_digest.py", {"cwd": str(root)})
            self.assertEqual(code, 0)
            self.assertIn("• Money", out)
        self.assertFalse((self.state / "digest").exists())

    def test_missing_markers_fail_loud(self) -> None:
        root = self.project(facts="# CRITICAL_FACTS\n\n• a fact but no markers\n")
        code, out, _ = self.run_hook("facts_digest.py", {"session_id": "s", "cwd": str(root)})
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("\U0001F534"))
        self.assertIn("NOT injected", out)

    def test_memtree_json_without_facts_fails_loud(self) -> None:
        root = self.project(facts=None)
        (root / ".memory" / "memtree.json").write_text("{}", encoding="utf-8")
        _, out, _ = self.run_hook("facts_digest.py", {"session_id": "s", "cwd": str(root)})
        self.assertIn("NOT injected", out)

    def test_found_from_subdirectory_and_worktree(self) -> None:
        root = self.project()
        sub = root / "services" / "billing"
        sub.mkdir(parents=True)
        _, out, _ = self.run_hook("facts_digest.py", {"cwd": str(sub)})
        self.assertIn("• Money", out)
        # linked git worktree elsewhere: .git file points into <main>/.git/worktrees/<name>
        (root / ".git" / "worktrees" / "wt1").mkdir(parents=True)
        wt = self.tmp / "elsewhere" / "wt1"
        wt.mkdir(parents=True)
        (wt / ".git").write_text(f"gitdir: {root / '.git' / 'worktrees' / 'wt1'}\n", encoding="utf-8")
        _, out, _ = self.run_hook("facts_digest.py", {"cwd": str(wt)})
        self.assertIn("• Money", out)

    def test_garbage_stdin_and_odd_session_id(self) -> None:
        root = self.project()
        code, out, raw = self.run_hook("facts_digest.py", {"session_id": "../../etc/x", "cwd": str(root)})
        self.assertEqual(code, 0)
        files = list((self.state / "digest").iterdir())
        self.assertEqual(len(files), 1)
        self.assertNotIn("/", files[0].name)


class PostCompactTest(TempCase):
    def test_reinjects_digest_writes_marker_and_shows_card(self) -> None:
        root = self.project()
        threads = root / ".memory" / "threads"
        threads.mkdir()
        old = threads / "old-line.md"
        old.write_text("# old-line\n## Goal and acceptance\n- old goal\n", encoding="utf-8")
        os.utime(old, (time.time() - 100, time.time() - 100))
        (threads / "invoice-retry.md").write_text("# invoice-retry\n## Goal and acceptance\n- retry once\n", encoding="utf-8")
        (threads / "_TEMPLATE.md").write_text("# template\n", encoding="utf-8")
        payload = {"session_id": "pc-1", "cwd": str(root), "source": "compact"}
        code, out, raw = self.run_hook("post_compact.py", payload)
        self.assertEqual(code, 0)
        self.assertIn("• Money", out)
        self.assertIn("summary above is lossy", out)
        self.assertIn("invoice-retry.md", out)
        self.assertIn("- retry once", out)
        self.assertNotIn("old goal", out)
        self.assertLessEqual(len(raw), BUDGET)
        # the next prompt must not inject the digest a second time
        _, out2, _ = self.run_hook("facts_digest.py", {"session_id": "pc-1", "cwd": str(root)})
        self.assertIn("injected earlier", out2)

    def test_closed_cards_are_skipped(self) -> None:
        root = self.project()
        threads = root / ".memory" / "threads"
        threads.mkdir()
        (threads / "done.md").write_text("CLOSED 2026-11-12 -> no event\n# done\n", encoding="utf-8")
        _, out, _ = self.run_hook("post_compact.py", {"session_id": "pc-2", "cwd": str(root), "source": "compact"})
        self.assertNotIn("done.md", out)
        self.assertIn("no open handoff card", out)

    def test_byte_budget_with_huge_card_and_digest(self) -> None:
        bullets = "\n".join(f"• 规则 {i}: 金额一律用整数分存储, never floats, see section {i}." for i in range(400))
        root = self.project(facts=f"<!-- DIGEST-START -->\n{bullets}\n<!-- DIGEST-END -->\n")
        threads = root / ".memory" / "threads"
        threads.mkdir()
        (threads / "big.md").write_text("# big\n" + ("交接卡内容 card body line\n" * 5000), encoding="utf-8")
        code, out, raw = self.run_hook("post_compact.py", {"session_id": "pc-3", "cwd": str(root), "source": "compact"})
        self.assertEqual(code, 0)
        self.assertLessEqual(len(raw), BUDGET)
        raw.decode("utf-8")  # valid UTF-8 after cutting
        self.assertIn("…truncated", out)
        self.assertIn("summary above is lossy", out)  # the reminder survives truncation

    def test_card_only_truncation_keeps_digest_whole(self) -> None:
        root = self.project()
        threads = root / ".memory" / "threads"
        threads.mkdir()
        (threads / "big.md").write_text("# big\n" + ("x" * 50_000), encoding="utf-8")
        _, out, raw = self.run_hook("post_compact.py", {"session_id": "pc-4", "cwd": str(root), "source": "compact"})
        self.assertLessEqual(len(raw), BUDGET)
        self.assertIn("• Only billing writes", out)
        self.assertIn("…truncated", out)
        self.assertIn("end of card", out)

    def test_ignores_other_sources_and_plain_dirs(self) -> None:
        root = self.project()
        code, _, raw = self.run_hook("post_compact.py", {"session_id": "x", "cwd": str(root), "source": "startup"})
        self.assertEqual((code, raw), (0, b""))
        plain = self.tmp / "plain"
        plain.mkdir()
        code, _, raw = self.run_hook("post_compact.py", {"session_id": "x", "cwd": str(plain), "source": "compact"})
        self.assertEqual((code, raw), (0, b""))


class ClipTest(unittest.TestCase):
    def test_clip_respects_budget_on_multibyte_text(self) -> None:
        text = "交接" * 3000
        for budget in (500, 501, 502, 503, 2000):
            out = mc.clip(text, budget, "f.md")
            self.assertLessEqual(len(out.encode("utf-8")), budget)
            self.assertIn("…truncated", out)
        self.assertEqual(mc.clip("short", 100), "short")


class HandoffReminderTest(TempCase):
    def transcript(self, *contexts: int, model: str = "claude-test-model") -> Path:
        entries = [assistant(f"msg_{i}", c, model=model) for i, c in enumerate(contexts)]
        entries.append(assistant(f"msg_{len(contexts) - 1}", contexts[-1], model=model))  # duplicate id
        return write_transcript(self.tmp / "t" / "sess.jsonl", entries)

    def remind(self, root: Path, path: Path, **env: str) -> str:
        code, out, _ = self.run_hook("ctx_handoff_reminder.py",
                                     {"session_id": "h-1", "cwd": str(root), "transcript_path": str(path)}, **env)
        self.assertEqual(code, 0)
        return out

    def test_steps_fire_once_each(self) -> None:
        root = self.project()
        self.assertEqual(self.remind(root, self.transcript(100_000, 300_000)), "")
        out = self.remind(root, self.transcript(300_000, 460_000))
        self.assertIn("460,000 tokens", out)
        self.assertIn("450K step", out)
        self.assertIn("never carries production or deploy authorization", out)
        self.assertEqual(self.remind(root, self.transcript(470_000, 500_000)), "")
        out = self.remind(root, self.transcript(500_000, 610_000))
        self.assertIn("600K step", out)
        self.assertEqual(self.remind(root, self.transcript(610_000, 620_000)), "")
        out = self.remind(root, self.transcript(620_000, 900_000))
        self.assertIn("750K step", out)

    def test_jump_reminds_highest_step_only_once(self) -> None:
        root = self.project()
        out = self.remind(root, self.transcript(100_000, 800_000))
        self.assertIn("750K step", out)
        self.assertEqual(self.remind(root, self.transcript(100_000, 610_000)), "")

    def test_200k_window_and_env_override(self) -> None:
        root = self.project()
        out = self.remind(root, self.transcript(50_000, 95_000), MEMTREE_CONTEXT_WINDOW="200000")
        self.assertIn("90K step", out)
        out = self.remind(root, self.transcript(95_000, 125_000), MEMTREE_CONTEXT_WINDOW="200000")
        self.assertIn("120K step", out)
        (self.state / "handoff" / "h-1").unlink()
        out = self.remind(root, self.transcript(10_000, 60_000), MEMTREE_HANDOFF_TOKENS="50000, 70000")
        self.assertIn("50K step", out)

    def test_silent_cases(self) -> None:
        root = self.project()
        path = self.transcript(100_000, 800_000)
        plain = self.tmp / "plain"
        plain.mkdir()
        code, out, raw = self.run_hook("ctx_handoff_reminder.py",
                                       {"session_id": "h-2", "cwd": str(plain), "transcript_path": str(path)})
        self.assertEqual((code, raw), (0, b""))
        code, out, raw = self.run_hook("ctx_handoff_reminder.py", {"cwd": str(root), "transcript_path": str(path)})
        self.assertEqual((code, raw), (0, b""))
        code, out, raw = self.run_hook("ctx_handoff_reminder.py",
                                       {"session_id": "h-3", "cwd": str(root), "transcript_path": str(self.tmp / "nope")})
        self.assertEqual((code, raw), (0, b""))

    def test_sidechain_and_zero_usage_entries_ignored(self) -> None:
        root = self.project()
        side = assistant("side", 900_000)
        side["isSidechain"] = True
        zero = assistant("zero", 110)
        zero["message"]["usage"] = {"input_tokens": 0, "output_tokens": 0}  # type: ignore[index]
        path = write_transcript(self.tmp / "t" / "s2.jsonl", [assistant("a", 300_000), side, zero])
        self.assertEqual(self.remind(root, path), "")


class ManifestTest(unittest.TestCase):
    def test_hooks_json_points_at_existing_files(self) -> None:
        cfg = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
        commands = [h["command"] for groups in cfg["hooks"].values() for g in groups for h in g["hooks"]]
        self.assertEqual(len(commands), 3)
        for cmd in commands:
            rel = cmd.split("${CLAUDE_PLUGIN_ROOT}/", 1)[1].rstrip('"')
            self.assertTrue((HOOKS.parent / rel).is_file(), rel)
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/', cmd)  # quoted for paths with spaces
        self.assertNotIn("PreToolUse", cfg["hooks"])
        self.assertEqual(cfg["hooks"]["SessionStart"][0]["matcher"], "compact")


if __name__ == "__main__":
    unittest.main()
