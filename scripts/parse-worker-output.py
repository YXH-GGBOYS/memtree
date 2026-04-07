#!/usr/bin/env python3
"""Parse Worker subagent JSONL output and split into per-file .memory/*.md documents.

Used in bootstrap Phase 3: splits `claude -p` stream-json output into individual
memory files. Supports both source file analysis and database table schema output.

Usage:
    python3 scripts/parse-worker-output.py [workers_dir]

Arguments:
    workers_dir: Path to directory containing worker-*.jsonl files.
                 Defaults to .memory/workers/
"""
from __future__ import annotations
import json, sys, re
from pathlib import Path


def parse_workers(workers_dir: Path, memory_dir: Path) -> tuple[int, int]:
    """Parse all worker JSONL files and extract .memory/ documents.

    Returns:
        Tuple of (total_files_extracted, total_errors).
    """
    total_files = 0
    total_errors = 0

    for jsonl_file in sorted(workers_dir.glob("worker-*.jsonl")):
        print(f"Processing {jsonl_file.name}...")

        # Extract final text result from stream-json
        text = ""
        for line in jsonl_file.read_text().splitlines():
            try:
                msg = json.loads(line)
                # Method 1: from result event (final output)
                if msg.get("type") == "result" and "result" in msg:
                    text = msg["result"]
                    break
                # Method 2: from assistant message content blocks
                if msg.get("type") == "assistant" and "content" in msg:
                    for block in msg["content"]:
                        if block.get("type") == "text":
                            text += block["text"]
            except json.JSONDecodeError:
                continue

        if not text:
            print(f"  WARNING: No text content found in {jsonl_file.name}")
            continue

        # Split by ---BEGIN FILE: xxx--- markers
        blocks = re.split(r'---BEGIN FILE:\s*(.+?)\s*---', text)
        # blocks: ['preamble', 'path1', 'content1', 'path2', 'content2', ...]

        file_count = 0
        for i in range(1, len(blocks), 2):
            file_path = blocks[i].strip()
            content = blocks[i + 1].strip()
            # Remove trailing ---END FILE---
            content = re.sub(r'\s*---END FILE---\s*$', '', content)

            # Remove potential yaml code block markers
            content = re.sub(r'^```ya?ml\s*', '', content)
            content = re.sub(r'\s*```\s*$', '', content)

            # Write to .memory/{path}.md
            out_path = memory_dir / f"{file_path}.md"

            # Path traversal check
            resolved = out_path.resolve()
            if not str(resolved).startswith(str(memory_dir.resolve())):
                print(f"  SKIP (path traversal blocked): {file_path}")
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                out_path.write_text(content + "\n")
                file_count += 1
            except Exception as e:
                print(f"  ERROR writing {out_path}: {e}")
                total_errors += 1

        total_files += file_count
        print(f"  Extracted {file_count} files from {jsonl_file.name}")

        # Also process DB table format (if present)
        db_blocks = re.split(r'---BEGIN DB TABLE:\s*(.+?)\s*---', text)
        for i in range(1, len(db_blocks), 2):
            table_path = db_blocks[i].strip()  # e.g., "schema.table_name"
            content = db_blocks[i + 1].strip()
            content = re.sub(r'\s*---END DB TABLE---\s*$', '', content)

            # schema.table -> db/schema/table.md
            parts = table_path.split(".")
            if len(parts) == 2:
                schema, table = parts
                out_path = memory_dir / "db" / schema / f"{table}.md"
            elif len(parts) == 3:
                db_name, schema, table = parts
                out_path = memory_dir / "db" / db_name / schema / f"{table}.md"
            else:
                out_path = memory_dir / "db" / f"{table_path.replace('.', '/')}.md"

            # Path traversal check
            resolved = out_path.resolve()
            if not str(resolved).startswith(str(memory_dir.resolve())):
                print(f"  SKIP (path traversal blocked): {table_path}")
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_text(content + "\n")
                total_files += 1
            except Exception as e:
                print(f"  ERROR writing {out_path}: {e}")
                total_errors += 1

    return total_files, total_errors


def main() -> None:
    workers_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".memory/workers")
    memory_dir = Path(".memory")

    if not workers_dir.exists():
        print(f"ERROR: Workers directory not found: {workers_dir}")
        sys.exit(1)

    total_files, total_errors = parse_workers(workers_dir, memory_dir)

    print(f"\nDone: extracted {total_files} files, {total_errors} errors")
    print(f"Total .memory/ files: {sum(1 for _ in memory_dir.rglob('*.md'))}")


if __name__ == "__main__":
    main()
