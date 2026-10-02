#!/usr/bin/env python3
"""
delegate.py - a zero-dependency headless coding worker.

Runs a cheap/free model over any OpenAI-compatible endpoint (OmniRoute, DeepSeek,
Kimi/Moonshot) as a small agentic loop. The worker can read, search, and edit files
in the current repo. The worker model itself CANNOT run shell commands or touch git.
The CLI harness can, but only via the caller-provided --verify and --commit flags
(never the model), so the trust boundary stays intact. It prints a summary of what
it did to stdout; step logs go to stderr.

Usage:
    delegate.py <backend> "<task>"
    delegate.py free "Add docstrings to every function in src/utils.py"
    delegate.py deepseek "Convert callbacks to async/await in api/client.py" --dir .
    delegate.py free --verify "npm test" --commit "feat: x" "Implement x per spec"

--verify runs the given command after the worker edits; a non-zero exit prints the
command output and exits 2 without committing. --commit stages all changes and
commits, but only when verify passed (or no --verify was set). This lets the
orchestrator hand off a task and get back a tested, committed result at no Claude
token cost, while the worker model itself still never runs shell or git.

Backends are defined in ~/.claude/delegate.config.json (see config.example.json).
Only the Python standard library is used, so this runs anywhere Python 3.8+ exists.
"""

import argparse
import base64
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Worker summaries and diffs often contain Unicode (arrows, em dashes, emoji).
# Windows consoles default to cp1252, which raises UnicodeEncodeError on print.
# Force UTF-8 with a safe fallback so output never crashes the run.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG = {
    "backends": {
        "free": {
            "base_url": "http://localhost:20128/v1",
            "api_key": "",
            "model": "auto/coding",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "model": "deepseek-chat",
        },
        "kimi": {
            "base_url": "https://api.moonshot.ai/v1",
            "api_key_env": "MOONSHOT_API_KEY",
            "model": "kimi-k2-0711-preview",
        },
        "nvidia": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key_env": "NVIDIA_API_KEY",
            "model": "nvidia/nemotron-3-super-120b-a12b",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "api_key": "",
            "model": "nvidia/nemotron-3.5-lightning:free",
            # Optional leaderboard attribution; OpenRouter reads these if present.
            "extra_headers": {
                "HTTP-Referer": "https://github.com/aayushpokhrel1/delegation-pipeline",
                "X-Title": "delegation-pipeline",
            },
        },
    },
    "max_steps": 40,
    "temperature": 0.2,
    "max_tokens": 4096,
    "request_timeout": 180,
}

# Backend used when the caller names none. `free` costs nothing and, measured over
# bench/tasks.json, reviewing its diff costs the same as reviewing a paid worker's.
# Its one weakness is finishing: the OmniRoute pool drains under sustained load
# (2026-10-01: 5 of 9 tasks back-to-back, the other 4 all passing when retried alone).
# So the default is free and the chain below carries the failures, rather than the
# caller having to guess which tier a task deserves.
DEFAULT_BACKEND = "free"

# One hop, deliberately. A chain that re-rolls through every configured backend would
# turn one dry pool into four slow failures before the caller hears about it.
FALLBACK_BACKEND = {"free": "deepseek"}


class BackendError(RuntimeError):
    """A backend could not be reached or kept failing. Carries how far the worker
    got, because escalating after edits have landed would run the next backend
    against a half-edited tree."""

    def __init__(self, message, edits=0, usage=None):
        super().__init__(message)
        self.edits = edits
        self.usage = usage or {}


def resolve_positionals(backend, task, known_backends):
    """Return (backend, task) with the default tier filled in.

    `backend` and `task` are both optional positionals, so `delegate "<task>"`
    binds the task to `backend` and argparse cannot tell the difference. When the
    first argument is not a configured backend and nothing followed it, it is the
    task. Without this, defaulting the backend made the common one-argument call
    fail with "Unknown backend '<your whole task>'".
    """
    if backend and backend not in known_backends and not task:
        return DEFAULT_BACKEND, backend
    return backend or DEFAULT_BACKEND, task


def fallback_for(name, cfg, model_override=None):
    """The backend to escalate to when `name` fails, or None.

    None when the caller pinned --model (a model id is backend-specific, so carrying
    it to another backend would 404), when no hop is defined, or when the hop is not
    configured on this machine. A hop with no credential on this machine is not
    offered either."""
    if model_override:
        return None
    nxt = FALLBACK_BACKEND.get(name)
    if (not nxt or nxt == name or nxt not in cfg.get("backends", {})
            or not backend_has_credential(cfg, nxt)):
        return None
    return nxt

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".claude", "delegate.config.json"
)

LEDGER_PATH = os.environ.get("DELEGATE_LEDGER") or os.path.join(
    os.path.expanduser("~"), ".claude", "delegate-usage.jsonl"
)
# Median T_review / T_do from bench/RESULTS.md: reviewing a worker's diff costs
# about 14.4% of what doing the task inline costs, so ~85.6% of an offloaded
# task's tokens never reach the Claude subscription.
#
# CAVEAT, and do not drop it from anything that prints a number derived here:
# this ratio was measured with BENCH_BASELINE on BOTH sides of the bench (the
# same model did the task inline AND reviewed the worker's diff), on nine small
# single-file tasks. Everything downstream applies it to *worker* tokens to
# predict *orchestrator* (Opus) tokens, which assumes deepseek and Opus spend
# comparable tokens on the same task. That assumption is untested. The
# direction is sound; the figure is indicative, not billing-grade. If you
# re-run the bench with --baseline opus, delete this paragraph.
REVIEW_RATIO = 0.144
# Model on both sides of the benchmark that produced REVIEW_RATIO.
BENCH_BASELINE = "deepseek-chat"
# Spread of the per-task savings in bench/RESULTS.md, published alongside the
# median so the headline figure is not mistaken for a precise one. A test
# asserts these still match that file, so re-running the benchmark and
# forgetting to update them turns the suite red.
BENCH_SAVINGS_MIN = 60.7
BENCH_SAVINGS_MAX = 89.7
BENCH_TASK_COUNT = 9
# A redacted copy of the ledger, committed so the published numbers can be
# recomputed by anyone. Repo names are private and never included.
SNAPSHOT_PATH = os.path.join("bench", "ledger-snapshot.jsonl")
# Dropped before publication. "error" holds a raw provider payload, which has
# carried gateway URLs and account hints, so it never goes in a committed file.
SNAPSHOT_DROP_FIELDS = ("repo", "error")
# Rough blended USD per 1M tokens actually paid on each worker tier.
# Backends not listed here are free tiers ($0).
WORKER_PRICE_PER_MTOK = {"deepseek": 0.28, "kimi": 2.0}
# Blended USD per 1M tokens for an Opus-class orchestrator, used only for the
# "equivalent value" line in --stats.
CLAUDE_PRICE_PER_MTOK = 15.0

# Files / dirs the worker should never wander into.
IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
               "dist", "build", ".next", ".mypy_cache", ".pytest_cache"}
MAX_READ_BYTES = 200_000
MAX_SEARCH_MATCHES = 200
MAX_IMAGE_BYTES = 8_000_000
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".gif": "image/gif", ".webp": "image/webp"}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
        except (OSError, ValueError) as e:
            die(f"Failed to read config at {CONFIG_PATH}: {e}")
        # Shallow-merge top level, deep-merge backends.
        for k, v in user.items():
            if k == "backends" and isinstance(v, dict):
                for name, bcfg in v.items():
                    cfg["backends"].setdefault(name, {})
                    cfg["backends"][name].update(bcfg)
            else:
                cfg[k] = v
    return cfg


def _is_local_backend(b):
    """True when this backend's base_url points at a local gateway (keyless)."""
    host = urllib.parse.urlparse(b.get("base_url", "")).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def backend_has_credential(cfg, name):
    """True when `name` is configured and usable on this machine: a local gateway
    needs no key, a remote one needs a non-empty api_key or api_key_env value.
    Never raises and never calls die()."""
    if name not in cfg["backends"]:
        return False
    b = cfg["backends"][name]
    if _is_local_backend(b):
        return True
    env = b.get("api_key_env")
    return bool(b.get("api_key") or (env and os.environ.get(env)))


def cold_start_help(cfg, name):
    """Guidance to append when `name` is a local backend that nothing is listening
    on, or "" when there is nothing useful to say."""
    if name not in cfg["backends"]:
        return ""
    b = cfg["backends"][name]
    if not _is_local_backend(b):
        return ""
    return (
        f"\n\nThe '{name}' backend talks to a local gateway at {b['base_url']}, "
        f"and nothing is listening there.\n"
        f"Three ways forward:\n"
        f"  1. Start the gateway, then run the same command again:\n"
        f"       npx --yes omniroute\n"
        f"  2. Use a remote backend instead: set one of DEEPSEEK_API_KEY, "
        f"OPENROUTER_API_KEY or\n"
        f"     NVIDIA_API_KEY in your environment, then re-run.\n"
        f"  3. Point '{name}' at any other OpenAI-compatible endpoint by editing\n"
        f"     {CONFIG_PATH} (start from config.example.json).\n"
    )


def resolve_backend(cfg, name):
    if name not in cfg["backends"]:
        die(f"Unknown backend '{name}'. Known: {', '.join(cfg['backends'])}")
    b = dict(cfg["backends"][name])
    key = b.get("api_key", "")
    env = b.get("api_key_env")
    if env:
        key = os.environ.get(env, key)
    b["api_key"] = key or ""
    # Local gateways (OmniRoute etc.) are keyless; only remote hosts need a key.
    host = urllib.parse.urlparse(b.get("base_url", "")).hostname or ""
    is_local = host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")
    if not is_local and not b["api_key"]:
        die(
            f"Backend '{name}' needs an API key. Set env var "
            f"'{b.get('api_key_env', 'API_KEY')}' or put 'api_key' in {CONFIG_PATH}."
        )
    return b


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #

def log(msg):
    print(msg, file=sys.stderr, flush=True)


def die(msg, code=1):
    print(f"delegate: error: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def record_run(entry):
    """Append one run to the JSONL ledger at LEDGER_PATH. Telemetry must never
    break a delegation, so every filesystem error is swallowed."""
    try:
        os.makedirs(os.path.dirname(LEDGER_PATH) or ".", exist_ok=True)
        with open(LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return True
    except (OSError, ValueError, TypeError):
        return False


def _attempt_entry(name, backend_cfg, err, started, escalated_to=None):
    """A ledger row for a backend attempt that FAILED. Written so a dry tier leaves
    a trace: before this existed, a failed run wrote nothing, and "never routed
    here" looked identical to "routed here and it died"."""
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": name,
        "model": backend_cfg.get("model"),
        "repo": os.path.basename(ROOT) or ROOT,
        "prompt": (err.usage or {}).get("prompt_tokens", 0),
        "completion": (err.usage or {}).get("completion_tokens", 0),
        "total": (err.usage or {}).get("total_tokens", 0),
        "calls": (err.usage or {}).get("calls", 0),
        "elapsed_s": round(time.monotonic() - started, 1),
        "ok": False,
        "error": str(err)[:300],
        "edits": err.edits,
        "escalated_to": escalated_to,
        "verify": None,
        "commit": None,
    }


def summarize_ledger(rows):
    """Aggregate ledger rows into the totals --stats prints. Pure: takes a list
    of dicts, returns a dict, touches no files."""
    prompt = completion = total = calls = 0
    worker_usd = 0.0
    verify_failed = 0
    commits = 0
    # Rows written before the "ok" field existed are all successes, so a missing
    # "ok" means True. Failed attempts are counted but kept out of the savings
    # math: tokens spent on a run that produced nothing are not an offload.
    failed = [r for r in rows if r.get("ok") is False]
    rows = [r for r in rows if r.get("ok") is not False]
    attempts_by_backend = {}
    for r in failed:
        slot = attempts_by_backend.setdefault(
            r.get("backend") or "unknown", {"failed": 0, "escalated": 0})
        slot["failed"] += 1
        if r.get("escalated_to"):
            slot["escalated"] += 1
    timestamps = []
    by_backend = {}
    by_model = {}
    by_repo = {}
    by_month = {}

    def _bump(group, key, row_total):
        slot = group.setdefault(key, {"runs": 0, "total": 0})
        slot["runs"] += 1
        slot["total"] += row_total

    for row in rows:
        row_prompt = row.get("prompt", 0) or 0
        row_completion = row.get("completion", 0) or 0
        row_total = row.get("total", 0) or 0
        prompt += row_prompt
        completion += row_completion
        total += row_total
        calls += row.get("calls", 0) or 0
        backend = row.get("backend") or "unknown"
        worker_usd += row_total / 1e6 * WORKER_PRICE_PER_MTOK.get(backend, 0.0)
        ts = row.get("ts")
        if ts:
            timestamps.append(ts)
        _bump(by_backend, backend, row_total)
        _bump(by_model, row.get("model") or "unknown", row_total)
        _bump(by_repo, row.get("repo") or "unknown", row_total)
        _bump(by_month, (ts or "unknown")[:7], row_total)
        if row.get("verify") == "failed":
            verify_failed += 1
        commit = row.get("commit")
        if isinstance(commit, str) and commit and commit != "skipped":
            commits += 1

    avoided = round(total * (1 - REVIEW_RATIO))
    return {
        "runs": len(rows),
        "failed_attempts": len(failed),
        "attempts_by_backend": attempts_by_backend,
        "prompt": prompt,
        "completion": completion,
        "total": total,
        "calls": calls,
        "first": min(timestamps) if timestamps else None,
        "last": max(timestamps) if timestamps else None,
        "worker_usd": worker_usd,
        "avoided": avoided,
        "avoided_usd": avoided / 1e6 * CLAUDE_PRICE_PER_MTOK,
        "by_backend": by_backend,
        "by_model": by_model,
        "by_repo": by_repo,
        "by_month": by_month,
        "verify_failed": verify_failed,
        "commits": commits,
    }


def read_ledger():
    """Return the ledger rows as a list of dicts. Missing file or corrupt lines
    yield fewer rows rather than an error."""
    rows = []
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows


def write_snapshot(rows, path=SNAPSHOT_PATH):
    """Write a redacted copy of the ledger for publication: every row minus the
    fields in SNAPSHOT_DROP_FIELDS, oldest first. Returns the number of rows
    written, or None when the destination directory does not exist (the tool
    runs in other repos too, and must not litter them)."""
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        return None
    ordered = sorted(rows, key=lambda row: row.get("ts") or "")
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for row in ordered:
                redacted = {k: v for k, v in row.items()
                            if k not in SNAPSHOT_DROP_FIELDS}
                f.write(json.dumps(redacted, sort_keys=True) + "\n")
    except OSError:
        return None
    return len(ordered)


def print_stats():
    """Read the ledger and print the running savings tally to stdout."""
    rows = read_ledger()

    if not rows:
        print(f"delegate usage ledger is empty (no runs recorded yet): {LEDGER_PATH}")
        return

    s = summarize_ledger(rows)
    pct = round((1 - REVIEW_RATIO) * 100, 1)
    print(f"delegate usage ledger: {LEDGER_PATH}")
    print(f"{s['runs']} runs from {s['first']} to {s['last']}")
    print()
    print(f"offloaded to workers   {format(s['total'], ',')} tokens over "
          f"{format(s['calls'], ',')} worker calls   (measured)")
    print(f"paid on worker tier    ${s['worker_usd']:.2f}")
    print(f"claude tokens avoided  ~{format(s['avoided'], ',')}   "
          f"({pct}% of offloaded, ratio from bench/RESULTS.md)")
    print(f"opus-equivalent value  ~${s['avoided_usd']:.2f}")
    print(f"  the two ~ rows are estimates: ratio measured {BENCH_BASELINE} on both")
    print(f"  sides of {BENCH_TASK_COUNT} bench tasks ({BENCH_SAVINGS_MIN}-{BENCH_SAVINGS_MAX}% spread), then applied to")
    print("  worker tokens as a stand-in for Opus token counts. Direction, not billing.")
    print(f"verify failures {s['verify_failed']}   commits {s['commits']}")
    if s["failed_attempts"]:
        parts = ", ".join(
            f"{k} {v['failed']} failed ({v['escalated']} escalated)"
            for k, v in sorted(s["attempts_by_backend"].items()))
        print(f"failed attempts {s['failed_attempts']}   {parts}")
        print("  (excluded from the totals above: a run that produced nothing is")
        print("   not an offload. A tier with 0 runs and 0 failed attempts was")
        print("   never routed to at all.)")
    print()

    for label, group in (("backend", s["by_backend"]), ("model", s["by_model"]),
                         ("repo", s["by_repo"]), ("month", s["by_month"])):
        print(f"by {label}:")
        width = max([len(k) for k in group] + [0])
        for key, slot in sorted(group.items(), key=lambda kv: -kv[1]["total"]):
            print(f"  {key.ljust(width)}   {format(slot['runs'], ',')} runs   "
                  f"{format(slot['total'], ',')} tokens")
        print()


# --------------------------------------------------------------------------- #
# README stats block (public-facing; never names a repo)
# --------------------------------------------------------------------------- #

START_MARKER = "<!-- delegate-stats:start -->"
END_MARKER = "<!-- delegate-stats:end -->"


def _bar(frac, width=20):
    """A fixed-width unicode bar for a 0..1 fraction."""
    if frac is None:
        frac = 0.0
    frac = min(1.0, max(0.0, frac))
    filled = round(frac * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def stats_markdown(s):
    """Render a summarize_ledger() result as a public-facing Markdown block.
    Pure: no file access, no repo names in the output, only a repo count."""
    runs = s["runs"]
    repos = len(s["by_repo"])
    total = s["total"]
    pct = round((1 - REVIEW_RATIO) * 100, 1)
    review_pct = round(REVIEW_RATIO * 100, 1)
    date = time.strftime("%Y-%m-%d", time.gmtime())

    lines = [
        "### Measured impact",
        "",
        f"_Generated {date} from {format(runs, ',')} delegated "
        f"{'run' if runs == 1 else 'runs'} across {repos} "
        f"{'repo' if repos == 1 else 'repos'}._",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Runs delegated | {format(runs, ',')} |",
        f"| Tokens offloaded to workers | {format(total, ',')} (measured) |",
        f"| Worker API calls | {format(s['calls'], ',')} |",
        f"| Paid on the worker tier | ${s['worker_usd']:.2f} |",
        f"| Claude tokens avoided | ~{format(s['avoided'], ',')} (estimated) |",
        f"| Opus-equivalent value | ~${s['avoided_usd']:.2f} |",
    ]

    if total:
        lines += ["", "By backend:", "", "```"]
        width = max([len(k) for k in s["by_backend"]] + [0])
        for key, slot in sorted(s["by_backend"].items(),
                                key=lambda kv: -kv[1]["total"]):
            frac = slot["total"] / total
            share = round(frac * 100)
            lines.append(f"{key.ljust(width)}  {_bar(frac)}  "
                         f"{str(share).rjust(3)}%   "
                         f"{format(slot['total'], ',')} tokens")
        lines += ["```", "", "By month:", "", "```"]
        width = max([len(k) for k in s["by_month"]] + [0])
        peak = max([slot["total"] for slot in s["by_month"].values()] + [0])
        for key, slot in sorted(s["by_month"].items()):
            frac = (slot["total"] / peak) if peak else 0.0
            lines.append(f"{key.ljust(width)}  {_bar(frac)}   "
                         f"{format(slot['total'], ',')} tokens")
        lines.append("```")

    lines += [
        "",
        "Offloaded tokens and worker calls are measured from each backend's own usage",
        f'fields. "Claude tokens avoided" is an estimate: {pct}% of the offloaded total,',
        f"the median of {BENCH_TASK_COUNT} benchmark tasks in "
        "[`bench/RESULTS.md`](bench/RESULTS.md)",
        f"whose individual savings ranged from {BENCH_SAVINGS_MIN}% to "
        f"{BENCH_SAVINGS_MAX}%. Reviewing a",
        f"worker's diff costs about {review_pct}% of doing the task inline. Dollar figures",
        "are rough blended per-tier prices, for scale, not billing.",
        "",
        f"That ratio was measured with `{BENCH_BASELINE}` on both sides of the benchmark:",
        "the same model did each task inline and reviewed the worker's diff. It is applied",
        "above to worker tokens as a stand-in for what the orchestrator model would have",
        "spent on the same work, which is an assumption the benchmark does not test. Read",
        "the direction as sound and the absolute figures as indicative.",
        "",
        "Every figure above can be recomputed from the redacted ledger committed at",
        "[`bench/ledger-snapshot.jsonl`](bench/ledger-snapshot.jsonl), using this exact",
        "command:",
        "",
        "`python delegate.py --stats --ledger bench/ledger-snapshot.jsonl`",
    ]
    return "\n".join(lines)


def replace_stats_region(text, block):
    """Return `text` with the content between the markers replaced by `block`.
    Returns None when either marker is missing. Idempotent: replacing twice with
    the same block yields the same text."""
    start = text.find(START_MARKER)
    if start < 0:
        return None
    end = text.find(END_MARKER, start + len(START_MARKER))
    if end < 0:
        return None
    return (text[:start + len(START_MARKER)] + "\n\n" + block + "\n\n"
            + text[end:])


def write_readme_stats(path="README.md"):
    """Refresh the stats block in `path` from the ledger."""
    rows = read_ledger()
    if not rows:
        print(f"delegate usage ledger is empty (no runs recorded yet): {LEDGER_PATH}")
        return
    block = stats_markdown(summarize_ledger(rows))
    # Refresh the published snapshot before the "already up to date" return, so
    # the snapshot and the README block can never drift apart.
    written = write_snapshot(rows)
    if written is not None:
        print(f"delegate: wrote {SNAPSHOT_PATH} ({format(written, ',')} rows, "
              f"repo names stripped)")
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
    except OSError as e:
        die(f"could not read {path}: {e}")
    new_text = replace_stats_region(text, block)
    if new_text is None:
        print(block)
        print()
        print(f"delegate: {path} has no stats markers. Paste these two lines into "
              f"the README once, then re-run:")
        print(f"  {START_MARKER}")
        print(f"  {END_MARKER}")
        return
    if new_text == text:
        print(f"delegate: stats block in {path} is already up to date")
        return
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
    except OSError as e:
        die(f"could not write {path}: {e}")
    print(f"delegate: refreshed stats block in {path} from "
          f"{format(len(rows), ',')} ledger run(s)")


# --------------------------------------------------------------------------- #
# File tools (sandboxed to ROOT)
# --------------------------------------------------------------------------- #

ROOT = os.getcwd()


def safe_path(rel):
    """Resolve `rel` under ROOT; refuse anything that escapes the repo."""
    if rel is None:
        raise ValueError("path is required")
    p = os.path.realpath(os.path.join(ROOT, rel))
    root = os.path.realpath(ROOT)
    if p != root and not p.startswith(root + os.sep):
        raise ValueError(f"path '{rel}' is outside the working directory")
    return p


def tool_list_dir(path="."):
    p = safe_path(path)
    if not os.path.isdir(p):
        return f"Not a directory: {path}"
    entries = []
    for name in sorted(os.listdir(p)):
        if name in IGNORE_DIRS:
            continue
        full = os.path.join(p, name)
        entries.append(name + ("/" if os.path.isdir(full) else ""))
    return "\n".join(entries) if entries else "(empty)"


def tool_find_files(pattern, path="."):
    base = safe_path(path)
    hits = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if fnmatch.fnmatch(fn, pattern):
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                hits.append(rel.replace(os.sep, "/"))
                if len(hits) >= MAX_SEARCH_MATCHES:
                    hits.append("... (truncated)")
                    return "\n".join(hits)
    return "\n".join(hits) if hits else "(no matches)"


def tool_read_file(path):
    p = safe_path(path)
    if not os.path.isfile(p):
        return f"Not a file: {path}"
    size = os.path.getsize(p)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        data = f.read(MAX_READ_BYTES)
    if size > MAX_READ_BYTES:
        data += f"\n... (truncated at {MAX_READ_BYTES} bytes of {size})"
    return data


def tool_write_file(path, content):
    p = safe_path(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content if content is not None else "")
    return f"Wrote {len(content or '')} chars to {path}"


def tool_edit_file(path, old_string, new_string, replace_all=False):
    p = safe_path(path)
    if not os.path.isfile(p):
        return f"Not a file: {path}"
    with open(p, "r", encoding="utf-8") as f:
        text = f.read()
    if old_string == new_string:
        return "No change: old_string and new_string are identical."
    count = text.count(old_string)
    if count == 0:
        return "old_string not found. Read the file and match exactly (incl. whitespace)."
    if count > 1 and not replace_all:
        return (f"old_string matches {count} times; it must be unique. "
                f"Add surrounding context, or pass replace_all=true.")
    text = text.replace(old_string, new_string)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return f"Edited {path} ({count} replacement{'s' if count != 1 else ''})."


def tool_search_text(pattern, path=".", glob="*"):
    base = safe_path(path)
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"Bad regex: {e}"
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if not fnmatch.fnmatch(fn, glob):
                continue
            fpath = os.path.join(dirpath, fn)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if rx.search(line):
                            rel = os.path.relpath(fpath, ROOT).replace(os.sep, "/")
                            out.append(f"{rel}:{i}: {line.rstrip()[:300]}")
                            if len(out) >= MAX_SEARCH_MATCHES:
                                out.append("... (truncated)")
                                return "\n".join(out)
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(out) if out else "(no matches)"


# OpenAI tool schemas exposed to the worker.
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories of a directory in the repo.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory, default '.'"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files by name glob (e.g. '*.py') recursively.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "description": "Root to search, default '.'"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file's contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Regex-search file contents. Returns path:line: text matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Python regex"},
                    "path": {"type": "string", "description": "Root, default '.'"},
                    "glob": {"type": "string", "description": "Filename glob, default '*'"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given full contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": ("Replace an exact substring in a file. old_string must match "
                            "byte-for-byte and be unique unless replace_all=true."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_image",
            "description": ("Attach an image so you can see it. Give a repo-relative file path "
                            "or an http(s) URL. The image appears as the next message. Use when "
                            "the task refers to a screenshot, mockup, diagram, or other image."),
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string",
                            "description": "Repo-relative image path or http(s) URL"},
                },
                "required": ["src"],
            },
        },
    },
]

TOOL_IMPL = {
    "list_dir": tool_list_dir,
    "find_files": tool_find_files,
    "read_file": tool_read_file,
    "search_text": tool_search_text,
    "write_file": tool_write_file,
    "edit_file": tool_edit_file,
}


def run_tool(name, args):
    fn = TOOL_IMPL.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return str(fn(**args))
    except TypeError as e:
        return f"Bad arguments for {name}: {e}"
    except Exception as e:  # noqa: BLE001 - report any tool failure to the model
        return f"Tool {name} failed: {e}"


# --------------------------------------------------------------------------- #
# HTTP: OpenAI-compatible chat/completions
# --------------------------------------------------------------------------- #

def _parse_response(raw):
    """Return a response dict from either a plain JSON body or an SSE stream.

    Most endpoints (and any honoring stream:false) return one JSON object. Some free
    routes stream `data: {...}` chunks regardless; reassemble those into the same shape.
    """
    raw = raw.lstrip()
    if not raw.startswith("data:"):
        return json.loads(raw)

    content_parts = []
    tool_calls = {}  # index -> {id, function:{name, arguments}}
    usage = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]" or not payload:
            continue
        try:
            chunk = json.loads(payload)
        except ValueError:
            continue
        if chunk.get("usage"):  # streamed usage lands in a late chunk
            usage = chunk["usage"]
        delta = (chunk.get("choices") or [{}])[0].get("delta", {})
        if delta.get("content"):
            content_parts.append(delta["content"])
        for tc in delta.get("tool_calls", []) or []:
            idx = tc.get("index", 0)
            slot = tool_calls.setdefault(
                idx, {"id": tc.get("id", f"call_{idx}"), "type": "function",
                      "function": {"name": "", "arguments": ""}}
            )
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function", {})
            if fn.get("name"):
                slot["function"]["name"] = fn["name"]
            if fn.get("arguments"):
                slot["function"]["arguments"] += fn["arguments"]
    message = {"role": "assistant", "content": "".join(content_parts)}
    if tool_calls:
        message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    out = {"choices": [{"message": message}]}
    if usage:
        out["usage"] = usage
    return out


# Some upstreams (behind Cloudflare) block the default urllib signature with a
# 1010 "browser_signature_banned" error. Send an explicit, honest User-Agent.
USER_AGENT = "delegate/1.0 (+https://github.com/aayushpokhrel1/delegation-pipeline)"


def _base_headers(backend):
    """Auth + User-Agent + any per-backend extra_headers (e.g. OpenRouter attribution)."""
    headers = {"User-Agent": USER_AGENT}
    if backend.get("api_key"):
        headers["Authorization"] = f"Bearer {backend['api_key']}"
    extra = backend.get("extra_headers")
    if isinstance(extra, dict):
        headers.update({str(k): str(v) for k, v in extra.items()})
    return headers


# --------------------------------------------------------------------------- #
# Vision: caller- or worker-supplied images -> OpenAI multimodal content
# --------------------------------------------------------------------------- #

def _guess_mime(src):
    ext = os.path.splitext(urllib.parse.urlparse(src).path)[1].lower()
    return IMAGE_MIME.get(ext, "image/png")


def load_image(src, allow_abs=False):
    """Return a `data:` URI for a local path or an http(s) URL.

    Local paths are sandboxed to ROOT unless allow_abs (caller-supplied --image may
    live anywhere, like --verify; the worker's view_image tool passes allow_abs=False).
    Raises ValueError on any failure so the caller/worker gets a clear message.
    """
    if not src or not str(src).strip():
        raise ValueError("image source is required")
    src = str(src).strip()
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": USER_AGENT}, method="GET")
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(MAX_IMAGE_BYTES + 1)
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        mime = ctype if ctype.startswith("image/") else _guess_mime(src)
    else:
        p = os.path.realpath(src) if allow_abs else safe_path(src)
        if not os.path.isfile(p):
            raise ValueError(f"not a file: {src}")
        with open(p, "rb") as f:
            data = f.read(MAX_IMAGE_BYTES + 1)
        mime = _guess_mime(src)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} bytes: {src}")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _image_part(uri):
    return {"type": "image_url", "image_url": {"url": uri}}


def build_user_content(text, image_uris):
    """Plain string when no images; OpenAI multimodal content array when images present."""
    if not image_uris:
        return text
    return [{"type": "text", "text": text}] + [_image_part(u) for u in image_uris]


def list_models(backend, timeout):
    """Print the model ids the backend exposes (GET /models)."""
    url = backend["base_url"].rstrip("/") + "/models"
    req = urllib.request.Request(url, headers=_base_headers(backend), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        die(f"listing models failed: HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    except (urllib.error.URLError, TimeoutError) as e:
        die(f"listing models failed: {e}")
    ids = sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))
    for i in ids:
        print(i)
    log(f"delegate: {len(ids)} model(s) available on backend")


def chat_completion(backend, messages, timeout):
    url = backend["base_url"].rstrip("/") + "/chat/completions"
    body = {
        "model": backend["model"],
        "messages": messages,
        "tools": TOOLS_SPEC,
        "tool_choice": "auto",
        # Force a single JSON body. Some gateways (e.g. OmniRoute's free routes)
        # stream SSE chunks unless told otherwise, which we can't parse here.
        "stream": False,
        "temperature": backend.get("temperature", DEFAULT_CONFIG["temperature"]),
        "max_tokens": backend.get("max_tokens", DEFAULT_CONFIG["max_tokens"]),
    }
    data = json.dumps(body).encode("utf-8")
    headers = _base_headers(backend)
    headers["Content-Type"] = "application/json"

    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            return _parse_response(raw)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            last_err = f"HTTP {e.code}: {detail}"
            # 401/403 often come from one bad provider in a load-balanced free
            # pool (missing key or a Cloudflare ban). Retrying re-rolls to a
            # different provider, so treat them as transient too.
            if e.code in (401, 403, 429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = f"connection error: {e}"
            time.sleep(1.5 * (attempt + 1))
    # Raise rather than die(): main() may still have a fallback backend to try.
    raise BackendError(f"request to {url} failed: {last_err}")


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """You are a headless coding worker operating inside a git repository.
You complete one delegated task, then stop. You have NO conversation history and NO
access to the human, so do not ask questions; make reasonable assumptions and proceed.

Rules:
- Use the provided tools to inspect and modify files. Read a file before editing it.
- You cannot run shell commands, install packages, run tests, or use git. Do not claim to.
- Make the smallest change that fully satisfies the task. Match the surrounding code's
  style, naming, and conventions. Do not reformat unrelated code.
- Prefer edit_file (exact-substring replace) for changes; use write_file for new files
  or full rewrites.
- If the task refers to an image you have not been shown, call view_image with its path or
  URL to see it. You can only see images you were given or fetched this way.
- When done, reply with a short plain-text SUMMARY: which files you changed and what you
  did, plus anything the reviewer should check or that you could not do. No tool call in
  your final message.
"""


def agent_loop(backend, task, max_steps, timeout, image_uris=None):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_content(
            f"TASK:\n{task}\n\nWorking directory: {ROOT}", image_uris)},
    ]
    edits = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    for step in range(1, max_steps + 1):
        try:
            resp = chat_completion(backend, messages, timeout)
        except BackendError as e:
            e.edits = edits
            e.usage = usage
            raise
        u = resp.get("usage") or {}
        if u:
            usage["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
            usage["completion_tokens"] += u.get("completion_tokens", 0) or 0
            usage["total_tokens"] += u.get("total_tokens", 0) or 0
            usage["calls"] += 1
        try:
            msg = resp["choices"][0]["message"]
        except (KeyError, IndexError):
            die(f"unexpected response: {json.dumps(resp)[:500]}")

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = (msg.get("content") or "").strip()
            log(f"[step {step}] done ({edits} edit(s) made)")
            return content or "(worker returned no summary)", usage

        # Append the assistant turn verbatim, then answer each tool call.
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })
        pending_images = []  # (src, uri) to attach as user turns after the tool replies
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            args = None
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except ValueError:
                result = f"Could not parse arguments as JSON: {raw_args[:200]}"
            if args is not None and name == "view_image":
                src = args.get("src")
                try:
                    uri = load_image(src)  # tool paths sandboxed to ROOT; urls allowed
                except Exception as e:  # noqa: BLE001 - report the failure to the model
                    result = f"view_image failed: {e}"
                else:
                    pending_images.append((src, uri))
                    result = f"Loaded image '{src}'. It is attached in the next message."
                log(f"[step {step}] view_image({str(src)[:60]}) -> {(result.splitlines() or [''])[0][:120]}")
            elif args is not None:
                result = run_tool(name, args)
                if name in ("write_file", "edit_file") and not result.lower().startswith(
                    ("no change", "not a file", "old_string", "bad ")
                ):
                    edits += 1
                log(f"[step {step}] {name}({_brief(args)}) -> {(result.splitlines() or [''])[0][:120]}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": result,
            })
        # OpenAI requires a tool reply per tool_call before any other role, so attach the
        # requested images as user turns only once all tool replies are in.
        for src, uri in pending_images:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": f"Image you requested via view_image('{src}'):"},
                _image_part(uri),
            ]})
    log(f"[step {max_steps}] hit step limit")
    return (f"Stopped after reaching the {max_steps}-step limit. {edits} edit(s) made so far.",
            usage)


def _brief(args):
    parts = []
    for k, v in args.items():
        s = str(v).replace("\n", " ")
        parts.append(f"{k}={s[:40]}")
    return ", ".join(parts)


# --------------------------------------------------------------------------- #
# Verify + commit (CLI harness only; the worker model never runs these)
# --------------------------------------------------------------------------- #

def run_verify(cmd, timeout):
    """Run the caller-provided verify command in ROOT. Returns (ok, output)."""
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"verify command timed out after {timeout}s"
    except Exception as e:  # noqa: BLE001
        return False, f"verify command could not run: {e}"
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode == 0, out


def git_commit(message):
    """Stage all changes and commit in ROOT. Returns (ok, info) where info is a
    short sha on success or the reason it was skipped/failed."""
    try:
        add = subprocess.run(["git", "add", "-A"], cwd=ROOT,
                             capture_output=True, encoding="utf-8", errors="replace")
        if add.returncode != 0:
            return False, (add.stderr or "git add failed").strip()
        # git diff --cached --quiet exits 0 when there is nothing staged.
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
            return False, "nothing to commit (worker made no committable change)"
        commit = subprocess.run(["git", "commit", "-m", message], cwd=ROOT,
                               capture_output=True, encoding="utf-8", errors="replace")
        if commit.returncode != 0:
            return False, (commit.stderr or commit.stdout or "git commit failed").strip()
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
        return True, sha
    except Exception as e:  # noqa: BLE001
        return False, f"git commit error: {e}"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        prog="delegate",
        description="Run a headless cheap-model worker over the current repo.",
    )
    parser.add_argument("backend", nargs="?", default=None,
                        help="Backend name (free, nvidia, deepseek, kimi, ...)")
    parser.add_argument("task", nargs="?", default=None,
                        help="The task instruction for the worker")
    parser.add_argument("--dir", default=None, help="Repo root (default: cwd)")
    parser.add_argument("--model", default=None, help="Override the model id")
    parser.add_argument("--image", action="append", default=None, metavar="PATH_OR_URL",
                        help="Attach an image (local path or http(s) URL) to the task. "
                             "Repeatable. Requires a vision-capable model.")
    parser.add_argument("--max-steps", type=int, default=None, help="Max agent steps")
    parser.add_argument("--list-models", action="store_true",
                        help="List the models this backend exposes, then exit")
    parser.add_argument("--stats", action="store_true",
                        help="Print the running token-savings tally from the "
                             "usage ledger, then exit")
    parser.add_argument("--ledger", default=None, metavar="PATH",
                        help="Read the usage ledger from PATH instead of "
                             "~/.claude/delegate-usage.jsonl")
    parser.add_argument("--readme", action="store_true",
                        help="With --stats: refresh the generated stats block in "
                             "README.md instead of printing to the terminal")
    parser.add_argument("--verify", default=None,
                        help="Command to run after editing (e.g. 'npm test'). "
                             "A non-zero exit prints the output and skips the commit.")
    parser.add_argument("--commit", default=None,
                        help="On success (verify passed, or no --verify) git add -A "
                             "and commit with this message.")
    args = parser.parse_args()

    global ROOT, LEDGER_PATH
    if args.ledger:
        LEDGER_PATH = args.ledger

    if args.stats:
        if args.readme:
            write_readme_stats()
        else:
            print_stats()
        return
    if args.dir:
        ROOT = os.path.realpath(args.dir)
        if not os.path.isdir(ROOT):
            die(f"--dir is not a directory: {args.dir}")

    cfg = load_config()

    args.backend, args.task = resolve_positionals(
        args.backend, args.task, cfg["backends"])

    backend = resolve_backend(cfg, args.backend)
    if args.model:
        backend["model"] = args.model
    backend.setdefault("temperature", cfg.get("temperature"))
    backend.setdefault("max_tokens", cfg.get("max_tokens"))
    max_steps = args.max_steps or cfg.get("max_steps", 40)
    timeout = cfg.get("request_timeout", 180)

    if args.list_models:
        list_models(backend, timeout)
        return
    if not args.task:
        die("a task is required (or pass --list-models to browse the catalog)")

    # Caller-supplied images may live anywhere (like --verify), so allow absolute paths.
    image_uris = []
    for src in (args.image or []):
        try:
            image_uris.append(load_image(src, allow_abs=True))
        except Exception as e:  # noqa: BLE001
            die(f"--image {src}: {e}")

    log(f"delegate: backend={args.backend} model={backend['model']} root={ROOT}"
        + (f" images={len(image_uris)}" if image_uris else ""))
    started = time.monotonic()

    # Try the chosen backend, then escalate once if it could not be reached. Only
    # escalate on a ZERO-edit failure: once the worker has written to the tree, the
    # next backend would start from a half-applied change nobody reviewed.
    used_backend, used_cfg = args.backend, backend
    escalated_from = None
    while True:
        try:
            summary, usage = agent_loop(
                used_cfg, args.task, max_steps, timeout, image_uris)
            break
        except BackendError as e:
            nxt = fallback_for(used_backend, cfg, args.model) if not e.edits else None
            record_run(_attempt_entry(used_backend, used_cfg, e, started,
                                      escalated_to=nxt))
            if not nxt:
                if e.edits:
                    die(f"{used_backend} failed after {e.edits} edit(s), so it was not "
                        f"escalated (the tree is half-edited; review it): {e}")
                die(f"{used_backend} failed and no fallback is available: {e}"
                    + cold_start_help(cfg, used_backend))
            log(f"delegate: {used_backend} failed with no edits made, escalating to "
                f"{nxt}: {e}")
            escalated_from, used_backend = used_backend, nxt
            used_cfg = resolve_backend(cfg, nxt)
            used_cfg.setdefault("temperature", cfg.get("temperature"))
            used_cfg.setdefault("max_tokens", cfg.get("max_tokens"))
            log(f"delegate: backend={used_backend} model={used_cfg['model']} root={ROOT}")

    # Worker tokens ran on the free/cheap backend, not the Claude subscription.
    # Emit this before verify/commit so the trailer survives a failed verify
    # (the benchmark reads it to tally offloaded work either way).
    if usage["calls"]:
        log(f"delegate: tokens prompt={usage['prompt_tokens']} "
            f"completion={usage['completion_tokens']} total={usage['total_tokens']} "
            f"over {usage['calls']} call(s)")
        summary += (f"\nTOKENS: prompt={usage['prompt_tokens']} "
                    f"completion={usage['completion_tokens']} "
                    f"total={usage['total_tokens']} calls={usage['calls']}")
    else:
        summary += "\nTOKENS: unavailable (backend returned no usage)"

    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": used_backend,
        "model": used_cfg["model"],
        # Written on every run so a later reader can tell "this tier was never tried"
        # from "it was tried and died" -- a distinction the ledger used to lose,
        # because a failed run wrote no row at all.
        "ok": True,
        "escalated_from": escalated_from,
        "repo": os.path.basename(ROOT) or ROOT,
        "prompt": usage["prompt_tokens"],
        "completion": usage["completion_tokens"],
        "total": usage["total_tokens"],
        "calls": usage["calls"],
        "elapsed_s": round(time.monotonic() - started, 1),
        "verify": None,
        "commit": None,
    }

    verify_ok = True
    if args.verify:
        log(f"delegate: verify: {args.verify}")
        verify_ok, out = run_verify(args.verify, timeout)
        tail = "\n".join(out.splitlines()[-40:])
        log(f"delegate: verify {'PASSED' if verify_ok else 'FAILED'}")
        entry["verify"] = "passed" if verify_ok else "failed"
        if not verify_ok:
            record_run(entry)
            print(summary)
            print(f"\n--- VERIFY FAILED: {args.verify} ---")
            print(tail)
            sys.exit(2)
        summary += f"\n--- VERIFY PASSED: {args.verify} ---"

    if args.commit and verify_ok:
        ok, info = git_commit(args.commit)
        log(f"delegate: commit {'ok ' + info if ok else 'skipped: ' + info}")
        entry["commit"] = info if ok else "skipped"
        summary += (f"\n--- COMMITTED {info} ---" if ok
                    else f"\n--- COMMIT SKIPPED: {info} ---")

    record_run(entry)
    print(summary)


if __name__ == "__main__":
    main()
