"""memq, token_report, verify_absence, who_reads, ctx_usage, memtree_init and install.sh on small fixtures."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import REPO, SCRIPTS, TempCase, assistant, tool_result, write_transcript  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import token_report  # noqa: E402

PITFALLS = """# billing PITFALLS

## P002 Webhook retry creates duplicate invoices
- status: ACTIVE
- trap: the payment webhook is retried and each retry creates an invoice; webhook retry is common
- how to verify: replay the same webhook id twice

## P001 Amounts in floats
- status: RESOLVED
- trap: float rounding on invoice totals
"""
INDEX = """# Events index

- EVT-20261101-001 | billing | duplicate invoice on webhook retry -> missing idempotency key | events/2026-11/EVT-20261101-001.md
- EVT-20261020-002 | auth | login loop -> cookie domain mismatch | events/2026-10/EVT-20261020-002.md
"""


class MemqTest(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.project()
        mem = self.root / ".memory"
        (mem / "billing").mkdir()
        (mem / "billing" / "PITFALLS.md").write_text(PITFALLS, encoding="utf-8")
        (mem / "events").mkdir()
        (mem / "events" / "INDEX.md").write_text(INDEX, encoding="utf-8")
        (mem / "threads").mkdir()
        (mem / "threads" / "_TEMPLATE.md").write_text("webhook retry template\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "runbook.md").write_text("# Runbook\nwebhook retry: check the queue\n", encoding="utf-8")
        (mem / "memtree.json").write_text(json.dumps({"extra_sources": ["docs/*.md", "../outside.md"]}), encoding="utf-8")

    def test_hit_with_cards_and_dedupe(self) -> None:
        code, out = self.run_script("memq.py", ["webhook", "retry"], self.root)
        self.assertEqual(code, 0, out)
        lines = [ln for ln in out.splitlines() if ln.startswith("[")]
        self.assertIn("[pitfalls] .memory/billing/PITFALLS.md:", out)
        self.assertIn("P002 Webhook retry creates duplicate invoices", out)
        self.assertIn("[events] .memory/events/INDEX.md:3", out)
        self.assertIn("[extra] docs/runbook.md:2", out)
        self.assertNotIn("_TEMPLATE", out)
        # P002 matches on its heading and its trap line, but is shown once
        self.assertEqual(sum("P002" in ln for ln in lines), 1)
        for ln in out.splitlines():
            if ln.startswith("    "):
                self.assertLessEqual(len(ln.strip()), 162)

    def test_all_words_must_match_and_only_filter(self) -> None:
        code, out = self.run_script("memq.py", ["cookie", "domain", "--only", "events"], self.root)
        self.assertEqual(code, 0)
        self.assertIn("EVT-20261020-002", out)
        code, out = self.run_script("memq.py", ["cookie", "invoice"], self.root)
        self.assertEqual(code, 1)
        self.assertIn("no match", out)

    def test_limit_and_no_memory(self) -> None:
        code, out = self.run_script("memq.py", ["invoice", "-n", "1"], self.root)
        self.assertEqual(code, 0)
        self.assertEqual(sum(ln.startswith("[") for ln in out.splitlines()), 1)
        self.assertIn("more; raise -n", out)
        plain = self.tmp / "plain"
        plain.mkdir()
        code, _ = self.run_script("memq.py", ["x"], plain)
        self.assertEqual(code, 2)


class TokenReportTest(TempCase):
    def make(self) -> Path:
        projects = self.tmp / "projects"
        big = "x" * 7000
        entries = [
            assistant("m1", 100_000, tool=("t1", "Read", {"file_path": "/work/app/src/a.py"})),
            tool_result("t1", big),
            assistant("m1", 100_000),  # same message id written twice: counted once
            assistant("m2", 350_000, tool=("t2", "Read", {"file_path": "/work/app/src/a.py"})),
            tool_result("t2", big),
            assistant("m3", 520_000, tool=("t3", "Bash", {"command": "git diff HEAD"})),
            tool_result("t3", "diff text " * 100),
            {"type": "system", "subtype": "compact_boundary"},
            assistant("m4", 120_000),
        ]
        write_transcript(projects / "-work-app" / "s1.jsonl", entries, cwd="/work/app")
        write_transcript(projects / "-work-lib" / "s2.jsonl", [assistant("n1", 90_000), assistant("n2", 95_000)],
                         cwd="/work/lib")
        write_transcript(projects / "-work-app" / "s1" / "subagents" / "agent-x.jsonl", [assistant("z", 50_000)])
        return projects

    def test_report_on_fixture(self) -> None:
        projects = self.make()
        code, out = self.run_script("token_report.py", ["--projects-dir", str(projects), "--since", "2000-01-01",
                                                        "--simulate", "300000:100000"], self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("2 main sessions, 6 calls, 1,275,000 context tokens", out)
        self.assertIn("1 subagent / workflow transcripts, or transcripts with no calls in the window", out)
        self.assertIn("| /work/app | 1 | 4 |", out)
        # app: 350K + 520K of 1,090K are in calls >300K; 520K of 1,090K >500K
        self.assertIn("| 80% | 48% | 100,000 | 520,000 |", out)
        self.assertIn("Read: code and other files", out)
        self.assertIn("Bash: git diff / show / log", out)
        self.assertIn("Same-file re-reads inside one session", out)
        self.assertIn("| 300,000 | 100,000 |", out)

    def test_window_uses_each_calls_timestamp(self) -> None:
        # Every file below was just written, so all pass the modification-time pre-filter; only the calls'
        # own timestamps decide what is counted. TZ=UTC makes "local midnight" the Z midnight.
        projects = self.tmp / "projects"

        def at(ts: str, mid: str, ctx: int, model: str = "claude-test-model") -> dict:
            return dict(assistant(mid, ctx, model=model), timestamp=ts)

        write_transcript(projects / "-work-app" / "s1.jsonl", [
            at("2026-10-09T23:59:59Z", "a1", 100_000),  # before --since; also the session's first call
            at("2026-10-10T00:00:00Z", "a2", 200_000),
            at("2026-10-12T00:00:00Z", "syn", 300_000, model="<synthetic>"),  # error placeholder, not a call
            at("2026-10-15T12:00:00Z", "a3", 400_000),
            at("2026-10-20T00:00:00Z", "a4", 600_000),  # at --until: excluded
        ], cwd="/work/app")
        write_transcript(projects / "-work-lib" / "s2.jsonl", [at("2026-09-01T00:00:00Z", "b1", 90_000)],
                         cwd="/work/lib")  # an old session whose file was touched later
        write_transcript(projects / "-work-new" / "s3.jsonl", [
            at("2026-10-11T00:00:00Z", "c1", 80_000), at("2026-10-12T00:00:00Z", "c2", 150_000)], cwd="/work/new")
        code, out = self.run_script("token_report.py", ["--projects-dir", str(projects), "--since", "2026-10-10",
                                                        "--until", "2026-10-20"], self.tmp, TZ="UTC")
        self.assertEqual(code, 0, out)
        self.assertIn("calls from 2026-10-10 to before 2026-10-20", out)
        self.assertIn("2 main sessions, 4 calls, 830,000 context tokens", out)
        self.assertNotIn("/work/lib", out)
        # app started before the window, so it has no first-call median; new started inside it
        self.assertIn("| /work/app | 1 | 2 | 72% | 67% | 0.0% | - | 400,000 |", out)
        self.assertIn("| /work/new | 1 | 2 | 28% | 0.0% | 0.0% | 80,000 | 150,000 |", out)
        self.assertIn("| **all** | 2 | 4 | 100% | 48% | 0.0% | 80,000 | 400,000 |", out)

    def test_old_session_touched_later_counts_zero_calls(self) -> None:
        # The file was just written (modified inside the window), but every call in it is older.
        path = write_transcript(self.tmp / "projects" / "-work-old" / "old.jsonl", [
            dict(assistant("o1", 120_000), timestamp="2026-09-01T10:00:00Z"),
            dict(assistant("o2", 350_000), timestamp="2026-10-09T23:59:59Z"),
        ], cwd="/work/old")
        lo = datetime(2026, 10, 10, tzinfo=timezone.utc).timestamp()
        s = token_report.parse(path, "main", "/work/old", lo, float("inf"))
        self.assertEqual(s.contexts, [])
        self.assertFalse(s.started_in_window)
        code, out = self.run_script("token_report.py", ["--projects-dir", str(self.tmp / "projects"),
                                                        "--since", "2026-10-10"], self.tmp, TZ="UTC")
        self.assertEqual(code, 1, out)
        self.assertIn("no main sessions with usage in that range", out)

    def test_forked_session_counted_once_in_the_older_file(self) -> None:
        # A fork carries its parent's calls (same message ids). The fork's name sorts first, but the parent
        # was created first, so the copied calls stay with the parent and only the fork's new call is its own.
        projects = self.tmp / "projects"
        parent = write_transcript(projects / "-work-app" / "z-parent.jsonl",
                                  [assistant("p1", 100_000), assistant("p2", 200_000)], cwd="/work/app")
        old = parent.stat().st_mtime - 100
        os.utime(parent, (old, old))
        write_transcript(projects / "-work-app" / "a-fork.jsonl",
                         [assistant("p1", 100_000), assistant("p2", 200_000), assistant("f1", 250_000)],
                         cwd="/work/fork")
        code, out = self.run_script("token_report.py", ["--projects-dir", str(projects), "--since", "2000-01-01"],
                                    self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("2 main sessions, 3 calls, 550,000 context tokens", out)
        self.assertIn("| /work/app | 1 | 2 |", out)
        self.assertIn("| /work/fork | 1 | 1 |", out)

    def test_simulate_function(self) -> None:
        sim = token_report.simulate
        self.assertEqual(sim([100, 200, 300], 1000, 50), 600)  # never crosses: unchanged
        # crosses 250 at 300: restart at 100, then grows by +100 per call as the original did
        self.assertEqual(sim([100, 200, 300, 400], 250, 100), 100 + 200 + 100 + 200)
        # a real compaction (drop to 120) never goes below min(x, restart)
        self.assertEqual(sim([100, 300, 120], 250, 100), 100 + 100 + 100)


class VerifyAbsenceTest(TempCase):
    def tree(self) -> Path:
        root = self.tmp / "tree"
        (root / "src").mkdir(parents=True)
        (root / "src" / "billing.py").write_text("def apply_refund_window(order):\n    return order\n", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "notes.md").write_text("We talk about RefundWindow here.\n", encoding="utf-8")
        (root / "node_modules" / "pkg").mkdir(parents=True)
        (root / "node_modules" / "pkg" / "x.js").write_text("ghostSymbol\n", encoding="utf-8")
        return root

    def test_walk_methods(self) -> None:
        root = self.tree()
        code, out = self.run_script("verify_absence.py", ["refund_window", "--no-git"], root)
        self.assertEqual(code, 0, out)
        self.assertIn("A fixed string: 1 hit lines (1 outside docs)", out)
        self.assertIn("B ignore-case variants: 2 hit lines (1 outside docs)", out)
        self.assertIn("refund[-_ ]?window", out)
        self.assertIn("EXISTS", out)
        code, out = self.run_script("verify_absence.py", ["ghostSymbol", "--no-git"], root)
        self.assertEqual(code, 1, out)
        self.assertIn("not found by either method", out)
        self.assertIn("Reproduce: python3 verify_absence.py ghostSymbol", out)

    @unittest.skipIf(shutil.which("git") is None, "git not installed")
    def test_git_methods_and_untracked(self) -> None:
        root = self.tree()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        code, out = self.run_script("verify_absence.py", ["refund_window"], root)
        self.assertEqual(code, 0, out)
        self.assertIn("git -C", out)
        self.assertIn("--untracked", out)
        self.assertIn("A fixed string: 1 hit lines", out)
        code, out = self.run_script("verify_absence.py", ["ghostSymbol"], root)
        self.assertEqual(code, 1, out)

    def test_bad_root_is_an_error(self) -> None:
        root = self.tree()
        code, out = self.run_script("verify_absence.py", ["x", "--no-git", "--roots", str(self.tmp / "missing")], root)
        self.assertEqual(code, 2)


class WhoReadsTest(TempCase):
    def test_groups(self) -> None:
        root = self.tmp / "svc"
        (root / "app").mkdir(parents=True)
        (root / "app" / "orders.py").write_text(
            "order.status = 'paid'\n"
            "if order.status == 'paid':\n"
            "    notify(order)\n"
            "rows = query.filter(Order.status.in_(['paid', 'refunded']))\n"
            "print(order.status)\n", encoding="utf-8")
        (root / "app" / "report.sql").write_text("UPDATE orders SET status = 'void' WHERE status = 'paid';\n", encoding="utf-8")
        (root / "README.md").write_text("status is documented here\n", encoding="utf-8")
        code, out = self.run_script("who_reads.py", ["status", "--no-git"], root)
        self.assertEqual(code, 0, out)
        writes = out.split("[writes]")[1].split("[conditions")[0]
        conds = out.split("[conditions")[1].split("[other]")[0]
        other = out.split("[other]")[1]
        self.assertIn("orders.py:1:", writes)
        self.assertIn("report.sql:1:", writes)
        self.assertIn("orders.py:2:", conds)
        self.assertIn("orders.py:4:", conds)
        self.assertIn("report.sql:1:", conds)
        self.assertIn("orders.py:5:", other)
        self.assertNotIn("README.md", out)
        code, out = self.run_script("who_reads.py", ["status", "--no-git", "--all-files"], root)
        self.assertIn("README.md", out)
        code, _ = self.run_script("who_reads.py", ["nothing_here", "--no-git"], root)
        self.assertEqual(code, 1)


class CtxUsageTest(TempCase):
    def test_reads_last_usage(self) -> None:
        path = write_transcript(self.tmp / "t.jsonl", [assistant("a", 150_000), assistant("b", 420_000)])
        code, out = self.run_script("ctx_usage.py", ["--json", "--transcript", str(path)], self.tmp)
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual(data["context_tokens"], 420_000)
        self.assertEqual(data["window"], 1_000_000)
        self.assertEqual(data["pct"], 42.0)
        code, out = self.run_script("ctx_usage.py", ["--transcript", str(path), "--window", "200000"], self.tmp)
        self.assertIn("420,000 / 200,000", out)

    def test_finds_project_folder_from_cwd(self) -> None:
        work = self.tmp / "my_app.v2"
        work.mkdir()
        folder = self.home / ".claude" / "projects" / str(work).replace("/", "-").replace("_", "-").replace(".", "-")
        write_transcript(folder / "x.jsonl", [assistant("a", 123_456)])
        code, out = self.run_script("ctx_usage.py", ["--json"], work)
        self.assertEqual(json.loads(out)["context_tokens"], 123_456, out)


class InitAndInstallTest(TempCase):
    def test_init_never_overwrites(self) -> None:
        proj = self.tmp / "proj"
        proj.mkdir()
        (proj / "CLAUDE.md").write_text("# My rules\n", encoding="utf-8")
        code, out = self.run_script("memtree_init.py", ["--project", str(proj), "--areas", "billing,api", "--claude-md"], proj)
        self.assertEqual(code, 0, out)
        facts = proj / ".memory" / "CRITICAL_FACTS.md"
        self.assertIn("<!-- DIGEST-START -->", facts.read_text(encoding="utf-8"))
        self.assertIn("# billing PITFALLS", (proj / ".memory" / "billing" / "PITFALLS.md").read_text(encoding="utf-8"))
        claude = (proj / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(claude.startswith("# My rules\n"))
        self.assertEqual(claude.count("<!-- memtree:begin -->"), 1)
        facts.write_text("mine\n", encoding="utf-8")
        code, out = self.run_script("memtree_init.py", ["--project", str(proj), "--areas", "billing", "--claude-md"], proj)
        self.assertEqual(facts.read_text(encoding="utf-8"), "mine\n")
        self.assertEqual((proj / "CLAUDE.md").read_text(encoding="utf-8").count("<!-- memtree:begin -->"), 1)
        self.assertIn("kept (already exists): .memory/CRITICAL_FACTS.md", out)
        code, out = self.run_script("memtree_init.py", ["--project", str(proj), "--areas", "../evil"], proj)
        self.assertEqual(code, 2)

    def test_snippet_is_short(self) -> None:
        lines = (REPO / "templates" / "CLAUDE.md.snippet").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 40)

    @unittest.skipIf(shutil.which("bash") is None, "bash not installed")
    def test_install_apply_is_idempotent_and_backs_up(self) -> None:
        home = self.tmp / "claude_home"
        home.mkdir()
        (home / "settings.json").write_text(json.dumps({"model": "m", "hooks": {"Stop": []}}), encoding="utf-8")
        env = self.env(CLAUDE_HOME=str(home))
        for _ in range(2):
            proc = subprocess.run(["bash", str(REPO / "install.sh"), "--apply"], capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["model"], "m")
        cmds = [h["command"] for g in settings["hooks"]["UserPromptSubmit"] for h in g["hooks"]]
        self.assertEqual(len(cmds), 2)
        self.assertEqual(len(settings["hooks"]["SessionStart"]), 1)
        self.assertTrue(list(home.glob("settings.json.memtree-backup-*")))
        skill = (home / "skills" / "memtree-lookup" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill)
        self.assertIn(str(home / "memtree" / "scripts" / "memq.py"), skill)

    def test_plugin_manifests(self) -> None:
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], "memtree")
        self.assertEqual(plugin["version"], "2.0.1")
        self.assertEqual(market["name"], "memtree")
        self.assertEqual(market["plugins"][0]["name"], plugin["name"])
        self.assertEqual(market["plugins"][0]["source"], "./")
        for skill in sorted((REPO / "skills").glob("*/SKILL.md")):
            head = skill.read_text(encoding="utf-8").split("---")[1]
            self.assertIn(f"name: {skill.parent.name}", head)
            self.assertIn("TRIGGER", head)
            self.assertIn("SKIP", head)


if __name__ == "__main__":
    unittest.main()
