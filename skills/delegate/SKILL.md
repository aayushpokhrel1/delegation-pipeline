---
name: delegate
description: "Use when a coding request contains work you can write a tight spec for and verify from a diff: boilerplate, scaffolding, repetitive edits, test stubs and docstrings, but equally a whole module from a clear contract, a real multi-file refactor, a non-trivial first-draft implementation or a clear-spec bug fix. Offloads it to a headless worker via the delegate CLI, then reviews the git diff. Do not route by hand: name no backend and the worker runs free ($0) and escalates to deepseek itself. The gate is a good spec, not low difficulty. Keeps design, tricky debugging, security-sensitive code, deep-context work, and one-liners in-session."
---

# delegate

Hand work to a cheap or free model worker so the paid Claude session spends its usage on
thinking, not typing. Not just mechanical work: anything you can specify precisely and check
from a diff, up to a whole module or a real refactor. The worker
(`~/.claude/bin/delegate`) is a zero-dependency
Python agent over any OpenAI-compatible endpoint. It can read, search, and edit files in the
current repo. It **cannot** run shell or git, by design: you review the resulting `git diff`
and commit.

Requires the CLI installed once (`bash install.sh` or `./install.ps1` from the repo). See
the [README](https://github.com/aayushpokhrel1/delegation-pipeline) for backends and keys.

## When to use

The gate is whether you can write a tight, verifiable spec, NOT how hard the task is.

**Do not route by hand. Name no backend.** `delegate "<task>"` runs on `free` ($0) and
escalates once to `deepseek` by itself if `free` cannot be reached. Measured on
`bench/tasks.json` (2026-10-01): reviewing a `free` diff costs the same as reviewing a paid
one (85.4% vs 85.6% median savings), so `free` is not the lower-quality tier, only the less
reliable one, and the escalation covers that. Hand-routing by "is this mechanical?" is what
left `free` at 0 runs across the first 45 delegations while everything went to the paid tier.

Name a backend only for a specific reason:

- **`deepseek`** when the task must not be retried from scratch, or when you are pinning
  `--model` (pinning disables escalation, since a model id belongs to one backend).
- **`openrouter`** to pin a `:free` or vision model. **`nvidia`** for a stronger free model
  than a `:free` id gives. **`kimi`** only if asked.

Keep in-session: architecture and design, writing the precise spec for each delegated task,
reviewing worker output, tricky debugging, security-sensitive code, deep-context work that
can't be specified in isolation, one-liners (the spec would cost more tokens than the edit).

## How to run

```
~/.claude/bin/delegate [backend] [--model <id>] "<task>"
```

The backend is optional and defaults to `free`, escalating once to `deepseek` on failure.
Both attempts land in the ledger, the failed one with `"ok": false` and `"escalated_to"`, so
a dry tier leaves a trace instead of looking like a tier nobody routed to.

Backends, when you do name one: `free` (OmniRoute, $0 local), `openrouter` (free `:free`
models, rate-limited, or cheap paid), `nvidia` (free trial credits, strong tool-calling
models), `deepseek` (cheap, ~Sonnet-class), `kimi` (premium, only if asked). Prefer
`openrouter` over `nvidia` so nvidia's finite credits stay in reserve. Tool-calling models
only; run `--list-models` and see `MODELS.md`.

For an image task (a mockup, screenshot, diagram), pass `--image <path|url>` with a
vision-capable model (e.g. `openrouter --model inclusionai/ling-3.0-flash-vl:free`); the
worker can also fetch images itself mid-task via its `view_image` tool.

Every run is tallied in a persistent ledger (`~/.claude/delegate-usage.jsonl`, override with
`DELEGATE_LEDGER`), and `delegate --stats` reports the running savings: offloaded tokens,
worker cost, and the estimated Claude tokens avoided.

## Protocol per delegated task

1. Write a tight, self-contained instruction: name the files, describe the change, point at
   a pattern to mirror. The worker has no conversation context.
2. Delegate on a clean tree so the resulting `git diff` is attributable.
3. Announce it in one line first (backend, model, what you are handing off).
4. After it returns, run `git diff` and **review**. Fix small issues yourself; re-delegate
   with a sharper spec if it drifted. Never trust an unreviewed edit.
5. You (not the worker) run tests and commit, after review.

Note: delegating sends repo content to external providers. Skip delegation for sensitive
repos, or when the user has said not to delegate this session.
