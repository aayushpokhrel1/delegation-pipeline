#!/usr/bin/env python3
"""
run_bench.py - measure how much orchestrator token cost the delegation pipeline saves.

For each task we run three measurements:
  * INLINE  (T_do)     - the baseline model does the work itself, via delegate.py.
  * WORKER  (T_worker) - the free/cheap backend does the work, via delegate.py.
  * REVIEW  (T_review) - the baseline model reviews the worker's diff.

savings% = 1 - T_review / T_do, both measured on the baseline model. The worker
tokens ran on the free/cheap tier, so they cost the orchestrator nothing.

Usage:
    python bench/run_bench.py
    python bench/run_bench.py --worker free --baseline deepseek --keep
"""

import argparse
import difflib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
DEFAULT_TASKS = os.path.join(HERE, "tasks.json")

sys.path.insert(0, REPO_ROOT)
import delegate  # noqa: E402 - needs REPO_ROOT on sys.path first

TOKENS_RE = re.compile(r"TOKENS:.*total=(\d+)")
DIFF_CAP = 6000

REVIEW_SYSTEM = ("You review a delegated coding change. Reply APPROVE if it satisfies "
                 "the brief, else list problems. Be brief.")


def parse_args():
    p = argparse.ArgumentParser(
        prog="run_bench",
        description="Benchmark the token savings of the delegation pipeline.",
    )
    p.add_argument("--worker", default="free",
                   help="Backend used for the real delegated-work arm (default: free)")
    p.add_argument("--baseline", default="deepseek",
                   help="Backend used to measure inline vs review asymmetry (default: deepseek)")
    p.add_argument("--tasks", default=DEFAULT_TASKS, help="Path to tasks.json")
    p.add_argument("--keep", action="store_true", help="Keep temp dirs")
    return p.parse_args()


def parse_tokens(stdout):
    m = TOKENS_RE.search(stdout or "")
    return int(m.group(1)) if m else 0


def run_delegate(backend, brief, tmp, verifycmd):
    """Run delegate.py in `tmp` and return (total_tokens, ok, stdout)."""
    cmd = [sys.executable, os.path.join(REPO_ROOT, "delegate.py"),
           backend, brief, "--dir", tmp, "--verify", verifycmd]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and "VERIFY PASSED" in (proc.stdout or "")
    return parse_tokens(proc.stdout), ok, out


def build_diff(tmp):
    """Unified diff of everything the worker changed in `tmp` vs FIXTURES."""
    chunks = []
    for dirpath, dirnames, filenames in os.walk(tmp):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".pytest_cache")]
        for fn in sorted(filenames):
            if fn.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, tmp).replace(os.sep, "/")
            base = os.path.join(FIXTURES, rel)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    new = f.read().splitlines()
            except OSError:
                continue
            if os.path.isfile(base):
                with open(base, "r", encoding="utf-8", errors="replace") as f:
                    old = f.read().splitlines()
            else:
                old = []
            if old == new:
                continue
            chunks.append("\n".join(difflib.unified_diff(
                old, new, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm="")))
    return "\n".join(chunks)[:DIFF_CAP]


def review_diff(backend, brief, diff, timeout):
    """Ask the baseline model to review the diff. Returns (tokens, error)."""
    messages = [
        {"role": "system", "content": REVIEW_SYSTEM},
        {"role": "user", "content": "BRIEF:\n" + brief + "\n\nDIFF:\n" + diff},
    ]
    try:
        resp = delegate.chat_completion(backend, messages, timeout)
        return resp.get("usage", {}).get("total_tokens", 0), None
    except Exception as e:  # noqa: BLE001 - a failed review must not abort the run
        return 0, f"review failed: {e}"


def measure_task(task, args, baseline_backend, timeout):
    verifycmd = args.verify_template.format(test=task["test"])
    row = {"id": task["id"], "tier": task["tier"], "t_do": 0, "t_worker": 0,
           "t_review": 0, "inline_ok": False, "worker_ok": False, "error": None}
    dirs = []
    try:
        inline_dir = tempfile.mkdtemp(prefix="bench_inline_")
        dirs.append(inline_dir)
        shutil.copytree(FIXTURES, inline_dir, dirs_exist_ok=True)
        row["t_do"], row["inline_ok"], _ = run_delegate(
            args.baseline, task["brief"], inline_dir, verifycmd)

        worker_dir = tempfile.mkdtemp(prefix="bench_worker_")
        dirs.append(worker_dir)
        shutil.copytree(FIXTURES, worker_dir, dirs_exist_ok=True)
        row["t_worker"], row["worker_ok"], _ = run_delegate(
            args.worker, task["brief"], worker_dir, verifycmd)

        diff = build_diff(worker_dir)
        row["t_review"], err = review_diff(baseline_backend, task["brief"], diff, timeout)
        if err:
            row["error"] = err
    except Exception as e:  # noqa: BLE001 - one bad task must not abort the run
        row["error"] = f"{type(e).__name__}: {e}"
    finally:
        if not args.keep:
            for d in dirs:
                shutil.rmtree(d, ignore_errors=True)
    return row


def savings_pct(t_do, t_review):
    if not t_do or not t_review:
        return None
    return round(100 * (1 - t_review / t_do), 1)


def median(values):
    vals = [v for v in values if v]
    return statistics.median(vals) if vals else 0


def fmt(v):
    return "-" if v is None else str(v)


def write_results(path, args, rows, medians, total_worker, stamp):
    lines = []
    lines.append("# Delegation benchmark results\n")
    lines.append(f"- Baseline backend: `{args.baseline}`  ")
    lines.append(f"- Worker backend: `{args.worker}`  ")
    lines.append(f"- Generated: {stamp}\n")
    lines.append(
        "Savings% = 1 - T_review / T_do, both measured on the baseline model. T_do is "
        "what the baseline spends doing the task inline; T_review is what it spends "
        "reviewing the worker's diff instead. The worker tokens (T_worker) ran on the "
        "free/cheap tier, so they cost the orchestrator nothing.\n")
    lines.append("| Task | Tier | Inline ok | Worker ok | T_do (inline) | "
                 "T_review (overhead) | Savings % | T_worker (offload) |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["id"], r["tier"], "yes" if r["inline_ok"] else "no",
            "yes" if r["worker_ok"] else "no", r["t_do"], r["t_review"],
            fmt(r["savings"]), r["t_worker"]))
    lines.append("")
    lines.append("Medians: T_do={} T_review={} T_worker={} savings={}%".format(
        medians["t_do"], medians["t_review"], medians["t_worker"], medians["savings"]))
    lines.append("")
    lines.append("Headline: median savings {}% with {} worker tokens offloaded.".format(
        medians["savings"], total_worker))
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    args = parse_args()

    with open(args.tasks, "r", encoding="utf-8") as f:
        spec = json.load(f)
    args.verify_template = spec["verify_template"]

    cfg = delegate.load_config()
    baseline_backend = delegate.resolve_backend(cfg, args.baseline)
    baseline_backend.setdefault("temperature", cfg.get("temperature"))
    baseline_backend.setdefault("max_tokens", cfg.get("max_tokens"))
    timeout = cfg.get("request_timeout", 180)

    rows = []
    for task in spec["tasks"]:
        print(f"bench: {task['id']} ({task['tier']}) ...", file=sys.stderr, flush=True)
        row = measure_task(task, args, baseline_backend, timeout)
        row["savings"] = savings_pct(row["t_do"], row["t_review"])
        rows.append(row)

    medians = {
        "t_do": median([r["t_do"] for r in rows]),
        "t_review": median([r["t_review"] for r in rows]),
        "t_worker": median([r["t_worker"] for r in rows]),
        "savings": round(median([r["savings"] for r in rows]), 1),
    }
    total_worker = sum(r["t_worker"] for r in rows)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    out_path = os.path.join(HERE, "RESULTS.md")
    write_results(out_path, args, rows, medians, total_worker, stamp)

    print(f"baseline={args.baseline} worker={args.worker} {stamp}")
    for r in rows:
        print("  {:<10} tier={:<11} inline_ok={:<3} worker_ok={:<3} "
              "T_do={:<6} T_review={:<6} savings={:<6} T_worker={}".format(
                  r["id"], r["tier"], str(r["inline_ok"]), str(r["worker_ok"]),
                  r["t_do"], r["t_review"], fmt(r["savings"]), r["t_worker"]))
        if r["error"]:
            print(f"    error: {r['error']}")
    print("Medians: T_do={} T_review={} T_worker={} savings={}%".format(
        medians["t_do"], medians["t_review"], medians["t_worker"], medians["savings"]))
    print(f"Headline: median savings {medians['savings']}% with "
          f"{total_worker} worker tokens offloaded.")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
