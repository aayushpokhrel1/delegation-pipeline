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
            "model": "deepseek-ai/deepseek-v4-flash-0731",
        },
    },
    "max_steps": 40,
    "temperature": 0.2,
    "max_tokens": 4096,
    "request_timeout": 180,
}

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".claude", "delegate.config.json"
)

# Files / dirs the worker should never wander into.
IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
               "dist", "build", ".next", ".mypy_cache", ".pytest_cache"}
MAX_READ_BYTES = 200_000
MAX_SEARCH_MATCHES = 200


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


def list_models(backend, timeout):
    """Print the model ids the backend exposes (GET /models)."""
    url = backend["base_url"].rstrip("/") + "/models"
    headers = {"User-Agent": USER_AGENT}
    if backend.get("api_key"):
        headers["Authorization"] = f"Bearer {backend['api_key']}"
    req = urllib.request.Request(url, headers=headers, method="GET")
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
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if backend.get("api_key"):
        headers["Authorization"] = f"Bearer {backend['api_key']}"

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
    die(f"request to {url} failed: {last_err}")


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
- When done, reply with a short plain-text SUMMARY: which files you changed and what you
  did, plus anything the reviewer should check or that you could not do. No tool call in
  your final message.
"""


def agent_loop(backend, task, max_steps, timeout):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"TASK:\n{task}\n\nWorking directory: {ROOT}"},
    ]
    edits = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
    for step in range(1, max_steps + 1):
        resp = chat_completion(backend, messages, timeout)
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
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except ValueError:
                result = f"Could not parse arguments as JSON: {raw_args[:200]}"
            else:
                result = run_tool(name, args)
                if name in ("write_file", "edit_file") and not result.lower().startswith(
                    ("no change", "not a file", "old_string", "bad ")
                ):
                    edits += 1
                log(f"[step {step}] {name}({_brief(args)}) -> {result.splitlines()[0][:120]}")
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": result,
            })
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
            cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
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
                             capture_output=True, text=True)
        if add.returncode != 0:
            return False, (add.stderr or "git add failed").strip()
        # git diff --cached --quiet exits 0 when there is nothing staged.
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
            return False, "nothing to commit (worker made no committable change)"
        commit = subprocess.run(["git", "commit", "-m", message], cwd=ROOT,
                               capture_output=True, text=True)
        if commit.returncode != 0:
            return False, (commit.stderr or commit.stdout or "git commit failed").strip()
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
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
    parser.add_argument("backend", help="Backend name (free, nvidia, deepseek, kimi, ...)")
    parser.add_argument("task", nargs="?", default=None,
                        help="The task instruction for the worker")
    parser.add_argument("--dir", default=None, help="Repo root (default: cwd)")
    parser.add_argument("--model", default=None, help="Override the model id")
    parser.add_argument("--max-steps", type=int, default=None, help="Max agent steps")
    parser.add_argument("--list-models", action="store_true",
                        help="List the models this backend exposes, then exit")
    parser.add_argument("--verify", default=None,
                        help="Command to run after editing (e.g. 'npm test'). "
                             "A non-zero exit prints the output and skips the commit.")
    parser.add_argument("--commit", default=None,
                        help="On success (verify passed, or no --verify) git add -A "
                             "and commit with this message.")
    args = parser.parse_args()

    global ROOT
    if args.dir:
        ROOT = os.path.realpath(args.dir)
        if not os.path.isdir(ROOT):
            die(f"--dir is not a directory: {args.dir}")

    cfg = load_config()
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

    log(f"delegate: backend={args.backend} model={backend['model']} root={ROOT}")
    summary, usage = agent_loop(backend, args.task, max_steps, timeout)

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

    verify_ok = True
    if args.verify:
        log(f"delegate: verify: {args.verify}")
        verify_ok, out = run_verify(args.verify, timeout)
        tail = "\n".join(out.splitlines()[-40:])
        log(f"delegate: verify {'PASSED' if verify_ok else 'FAILED'}")
        if not verify_ok:
            print(summary)
            print(f"\n--- VERIFY FAILED: {args.verify} ---")
            print(tail)
            sys.exit(2)
        summary += f"\n--- VERIFY PASSED: {args.verify} ---"

    if args.commit and verify_ok:
        ok, info = git_commit(args.commit)
        log(f"delegate: commit {'ok ' + info if ok else 'skipped: ' + info}")
        summary += (f"\n--- COMMITTED {info} ---" if ok
                    else f"\n--- COMMIT SKIPPED: {info} ---")

    print(summary)


if __name__ == "__main__":
    main()
