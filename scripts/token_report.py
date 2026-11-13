#!/usr/bin/env python3
"""Where did your Claude Code context tokens go? A local report from your own session transcripts.

Reads ~/.claude/projects/**/*.jsonl (or --projects-dir) on this machine and prints Markdown.
It never sends anything anywhere.

What it reports:
  1. Per project: sessions, calls, share of all re-sent context, how much of it was sent in calls whose
     context was above 300K / 500K tokens, the median first-call context (fixed overhead of a fresh
     session), and the largest context seen.
  2. Carry by content source: for each piece of content (a tool result, a hook injection, a message),
     its size x the number of later calls it stayed in context. Compaction resets the count. This shows
     what kind of content is expensive because it sits in a long session, not because it is big once.
  3. Files that were Read in 3 or more different sessions (candidates for a short summary or a card).
  4. Same-file re-reads inside one session, as a share of all context (usually tiny).
  5. A handoff simulation: if every session had been handed off to a fresh one when its context passed
     a threshold T, restarting at R, how much less context would have been re-sent?

How it counts:
  * Context of a call = input_tokens + cache_read_input_tokens + cache_creation_input_tokens, taken from
    the transcript (real numbers), deduplicated by message id.
  * Per-source sizes in (2)-(4) are estimates from character counts (CJK characters ~1.2 tokens, other
    characters ~3.5 per token). Use them to compare sources with each other, not as exact totals.
  * The simulation ignores what a handoff costs: the card, re-reading files in the new session, and any
    information lost. Treat its result as an upper bound.
  * Subagent / workflow transcripts are counted separately and left out of the main tables.
  * The time window (--since / --until, local midnight, --until excluded) is applied to each call's own
    timestamp. A file's modification time is only a pre-filter: Claude Code can append metadata lines to
    a transcript long after its last call, so "files modified since X" also picks up sessions whose calls
    are all older than X.
  * The same call can appear in several transcripts: a forked or copied session carries its parent's
    history with the same message ids. Each message id is counted once, in the transcript created first.
  * `<synthetic>` placeholder messages (written on errors, usage all zero) are not calls.
  * The first-call median only includes sessions whose first call falls inside the window.

Examples:
  python3 token_report.py --since 2026-10-01
  python3 token_report.py --since 2026-10-01 --until 2026-10-22
  python3 token_report.py --project my-app --out report.md --simulate 400000:120000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterator, List, Optional, Set, Tuple

CJK = re.compile(r"[　-鿿가-힯＀-￯]")
WORKTREE = re.compile(r"/\.claude/worktrees/[^/]+")
KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
DEFAULT_SIMS = ((600_000, 150_000), (450_000, 150_000), (450_000, 200_000))


def est(text: str) -> int:
    cjk = len(CJK.findall(text))
    return int(cjk * 1.2 + (len(text) - cjk) / 3.5)


def as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for c in content:
            if isinstance(c, dict):
                out.append(c.get("text", "") if c.get("type") == "text" else as_text(c.get("content")))
        return "\n".join(out)
    return ""


BASH_KINDS = [
    (r"pytest|unittest|npm (run )?test|vitest|jest|tsc\b|go test|cargo (test|build)|make\b|py_compile", "Bash: tests / builds"),
    (r"\bgit (diff|show|log)\b", "Bash: git diff / show / log"),
    (r"\bgit\b", "Bash: git, other"),
    (r"\.memory/", "Bash: reading .memory"),
    (r"\b(grep|rg|ag|find)\b", "Bash: grep / find"),
    (r"\b(cat|sed -n|head|tail|awk|less)\b", "Bash: printing files"),
    (r"\b(ssh|docker|kubectl)\b", "Bash: remote / containers"),
    (r"\bpython3?\b|\bnode\b", "Bash: scripts"),
]


def bash_kind(cmd: str) -> str:
    for pattern, name in BASH_KINDS:
        if re.search(pattern, cmd):
            return name
    return "Bash: other"


def read_kind(path: str) -> str:
    if "/.memory/" in path:
        return "Read: .memory"
    if path.endswith((".md", ".txt", ".rst")):
        return "Read: docs (.md/.txt)"
    return "Read: code and other files"


def project_of(transcript: Path) -> str:
    home = str(Path.home())
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"cwd"' not in line:
                continue
            try:
                cwd = json.loads(line).get("cwd") or ""
            except (ValueError, AttributeError):
                continue
            if cwd:
                return WORKTREE.sub("", cwd).replace(home, "~")
    return transcript.parent.name


@dataclass
class Session:
    project: str
    kind: str
    contexts: List[int] = field(default_factory=list)
    carry: DefaultDict[str, int] = field(default_factory=lambda: defaultdict(int))
    reads: List[Tuple[str, int]] = field(default_factory=list)
    started_in_window: Optional[bool] = None  # was the session's first call inside the window?


def in_window(entry: Dict[str, Any], lo: float, hi: float) -> bool:
    """True if the entry's own timestamp is in [lo, hi). Entries without a usable timestamp count as inside."""
    ts = entry.get("timestamp")
    if not isinstance(ts, str) or not ts:
        return True
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return True
    return lo <= t < hi


def parse(transcript: Path, kind: str, project: str, lo: float = 0.0, hi: float = float("inf"),
          seen: Optional[Set[str]] = None) -> Session:
    """Parse one transcript. Calls outside [lo, hi) are skipped; pass one shared `seen` set for all
    transcripts so a call copied into a forked session is counted only once."""
    s = Session(project=project, kind=kind)
    seen = set() if seen is None else seen
    tools: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    segment: List[Tuple[str, int, int]] = []  # (source, tokens, index of the next call)

    def flush() -> None:
        n = len(s.contexts)
        for cat, tok, at in segment:
            s.carry[cat] += tok * max(0, n - at)
        segment.clear()

    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict) or d.get("isSidechain"):
                continue
            t = d.get("type")
            if t == "system" and d.get("subtype") == "compact_boundary":
                flush()
                continue
            if t == "attachment":
                a = d.get("attachment") or {}
                if isinstance(a, dict) and "hook" in str(a.get("type", "")):
                    payload = a.get("content") or a.get("stdout") or ""
                    segment.append(("hook injections", est(json.dumps(payload, ensure_ascii=False)), len(s.contexts)))
                continue
            msg = d.get("message") or {}
            if not isinstance(msg, dict):
                continue
            if t == "assistant":
                usage = msg.get("usage") or {}
                mid = str(msg.get("id") or d.get("requestId") or "")
                total = sum(int(usage.get(k) or 0) for k in KEYS) if isinstance(usage, dict) else 0
                if total > 0 and msg.get("model") != "<synthetic>" and mid not in seen:
                    inside = in_window(d, lo, hi)
                    if s.started_in_window is None:
                        s.started_in_window = inside
                    if inside:
                        seen.add(mid)
                        s.contexts.append(total)
                for c in msg.get("content") or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        tools[str(c.get("id"))] = (str(c.get("name") or "?"), c.get("input") or {})
                        segment.append((f"assistant tool call: {c.get('name')}",
                                        est(json.dumps(c.get("input"), ensure_ascii=False)), len(s.contexts)))
                    elif c.get("type") in ("text", "thinking"):
                        segment.append(("assistant text", est(c.get("text") or c.get("thinking") or ""), len(s.contexts)))
            elif t == "user":
                content = msg.get("content")
                if isinstance(content, str):
                    segment.append(("user messages / reminders", est(content), len(s.contexts)))
                    continue
                for c in content or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text":
                        segment.append(("user messages / reminders", est(c.get("text", "")), len(s.contexts)))
                        continue
                    if c.get("type") != "tool_result":
                        continue
                    name, inp = tools.get(str(c.get("tool_use_id")), ("?", {}))
                    tok = est(as_text(c.get("content")))
                    if name == "Read":
                        path = WORKTREE.sub("", str(inp.get("file_path", "")))
                        cat = read_kind(path)
                        if in_window(d, lo, hi):
                            s.reads.append((path, tok))
                    elif name == "Bash":
                        cat = bash_kind(str(inp.get("command", "")))
                    elif name in ("Agent", "Task"):
                        cat = "subagent reports"
                    elif name.startswith("mcp__"):
                        cat = "MCP: " + name.split("__")[1][:24]
                    else:
                        cat = "tool: " + name
                    segment.append((cat, tok, len(s.contexts)))
    flush()
    return s


def transcripts(root: Path, since_ts: float, project_filter: Optional[str]) -> Iterator[Tuple[Path, str, str]]:
    """Transcripts modified since `since_ts` (a pre-filter only), oldest-created first, so a call copied into
    a forked session is attributed to the session it came from."""
    found: List[Tuple[float, str, Path]] = []
    for p in root.rglob("*.jsonl"):
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_mtime >= since_ts:
            found.append((getattr(st, "st_birthtime", st.st_mtime), p.as_posix(), p))
    for _, sp, p in sorted(found):
        kind = "subagent" if ("/subagents/" in sp or "/workflows/" in sp or p.name.startswith("agent-")) else "main"
        project = project_of(p)
        if project_filter and project_filter not in project:
            continue
        yield p, kind, project


def simulate(contexts: List[int], threshold: int, restart: int) -> int:
    """Re-sent context if the session had handed off to a fresh one at `threshold`, restarting at `restart`."""
    total, offset = 0, 0
    for x in contexts:
        y = x - offset
        if y > threshold:  # hand off: the new session starts at `restart` and grows as the old one did
            offset, y = x - restart, restart
        floor = min(x, restart)
        if y < floor:  # the real session shrank (compaction); a session never starts below `floor`
            offset, y = x - floor, floor
        total += y
    return total


def pct(a: float, b: float) -> str:
    if not b:
        return "-"
    v = a / b
    return "<0.1%" if 0 < v < 0.001 else f"{v:.1%}" if v < 0.1 else f"{v:.0%}"


def first_median(ss: List[Session]) -> str:
    first = sorted(s.contexts[0] for s in ss if s.started_in_window)
    return f"{first[len(first) // 2]:,}" if first else "-"


def report(sessions: List[Session], window: str, top: int, sims: List[Tuple[int, int]]) -> str:
    mains = [s for s in sessions if s.kind == "main" and s.contexts]
    grand = sum(sum(s.contexts) for s in mains)
    calls = sum(len(s.contexts) for s in mains)
    lines = [f"# Context token report ({window}; generated {datetime.now():%Y-%m-%d %H:%M} local)", "",
             f"{len(mains)} main sessions, {calls:,} calls, {grand:,} context tokens re-sent in total "
             f"({grand // max(calls, 1):,} per call on average).",
             f"{len(sessions) - len(mains)} subagent / workflow transcripts, or transcripts with no calls in the window, "
             "are not included below.", "",
             "## By project", "",
             "| project | sessions | calls | share | in calls >300K | in calls >500K | first-call median | max |",
             "|---|---|---|---|---|---|---|---|"]
    by_proj: DefaultDict[str, List[Session]] = defaultdict(list)
    for s in mains:
        by_proj[s.project].append(s)
    for proj, ss in sorted(by_proj.items(), key=lambda kv: -sum(sum(s.contexts) for s in kv[1])):
        ctx = [x for s in ss for x in s.contexts]
        tot = sum(ctx)
        lines.append(f"| {proj} | {len(ss)} | {len(ctx):,} | {pct(tot, grand)} | {pct(sum(x for x in ctx if x > 300_000), tot)} "
                     f"| {pct(sum(x for x in ctx if x > 500_000), tot)} | {first_median(ss)} | {max(ctx):,} |")
    allctx = [x for s in mains for x in s.contexts]
    lines.append(f"| **all** | {len(mains)} | {calls:,} | 100% | {pct(sum(x for x in allctx if x > 300_000), grand)} "
                 f"| {pct(sum(x for x in allctx if x > 500_000), grand)} | {first_median(mains)} | {max(allctx):,} |")

    carry: DefaultDict[str, int] = defaultdict(int)
    for s in mains:
        for k, v in s.carry.items():
            carry[k] += v
    ctot = sum(carry.values())
    lines += ["", "## Carry by content source (size x later calls it stayed in context; estimated)", "",
              "| source | share of carry |", "|---|---|"]
    lines += [f"| {k} | {pct(v, ctot)} |" for k, v in sorted(carry.items(), key=lambda kv: -kv[1])[:top]]

    reads: DefaultDict[str, List[int]] = defaultdict(lambda: [0, 0])
    read_sessions: DefaultDict[str, Set[int]] = defaultdict(set)
    reread_tok = 0
    for i, s in enumerate(mains):
        seen_here: Set[str] = set()
        for path, tok in s.reads:
            reads[path][0] += 1
            reads[path][1] += tok
            read_sessions[path].add(i)
            if path in seen_here:
                reread_tok += tok
            seen_here.add(path)
    multi = sorted(((v[1], v[0], len(read_sessions[p]), p) for p, v in reads.items() if len(read_sessions[p]) >= 3),
                   reverse=True)[:top]
    home = str(Path.home())
    lines += ["", "## Files Read in 3 or more sessions", "", "| file | reads / sessions | tokens (estimated) |", "|---|---|---|"]
    lines += [f"| {p.replace(home, '~')} | {n} / {ns} | {tok:,} |" for tok, n, ns, p in multi] or ["| (none) | | |"]
    lines += ["", f"Same-file re-reads inside one session: about {reread_tok:,} tokens, {pct(reread_tok, grand)} of all re-sent "
              "context (estimated size of the repeated Read results).", "",
              "## Handoff simulation", "",
              "Every session hands off when its context passes T and the new session starts at R, then grows as the "
              "original did. Ignores the handoff's own cost and any information lost, so read it as an upper bound.", "",
              "| T (handoff at) | R (fresh start) | less context re-sent |", "|---|---|---|"]
    for threshold, restart in sims:
        sim = sum(simulate(s.contexts, threshold, restart) for s in mains)
        lines.append(f"| {threshold:,} | {restart:,} | {pct(grand - sim, grand)} |")
    return "\n".join(lines) + "\n"


def parse_sim(text: str) -> Tuple[int, int]:
    t, r = text.split(":", 1)
    return int(t), int(r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="YYYY-MM-DD (local time): only calls from this day's midnight on; default: 21 days ago")
    ap.add_argument("--until", help="YYYY-MM-DD (local time): only calls before this day's midnight; default: now")
    ap.add_argument("--project", help="only projects whose path contains this text")
    ap.add_argument("--projects-dir", help="transcript root (default: ~/.claude/projects)")
    ap.add_argument("--out", help="write the Markdown here instead of printing it")
    ap.add_argument("--top", type=int, default=15, help="rows per table (default 15)")
    ap.add_argument("--simulate", action="append", type=parse_sim, metavar="T:R",
                    help="extra handoff simulation, e.g. 400000:120000 (repeatable)")
    args = ap.parse_args()

    since = datetime.strptime(args.since, "%Y-%m-%d") if args.since else datetime.now() - timedelta(days=21)
    until = datetime.strptime(args.until, "%Y-%m-%d").timestamp() if args.until else float("inf")
    root = Path(args.projects_dir).expanduser() if args.projects_dir else Path.home() / ".claude" / "projects"
    if not root.is_dir():
        print(f"token_report: no transcript folder at {root}", file=sys.stderr)
        return 1
    seen: Set[str] = set()  # shared across transcripts: drops calls a forked / copied session carried over
    sessions = [parse(p, kind, proj, since.timestamp(), until, seen)
                for p, kind, proj in transcripts(root, since.timestamp(), args.project)]
    if not any(s.kind == "main" and s.contexts for s in sessions):
        print("token_report: no main sessions with usage in that range", file=sys.stderr)
        return 1
    window = f"calls from {since:%Y-%m-%d}" + (f" to before {args.until}" if args.until else "")
    out = report(sessions, window, args.top, list(DEFAULT_SIMS) + (args.simulate or []))
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({out.count(chr(10))} lines)")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
