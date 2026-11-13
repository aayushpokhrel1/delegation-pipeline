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

This copy of the plugin ships instructions only: the `~/.claude/bin/delegate` worker is not
included. If `~/.claude/bin/delegate` does not exist, tell the user to set it up themselves
(do not run it for them): clone https://github.com/aayushpokhrel1/delegation-pipeline and run its
`install.sh` (or `install.ps1` on Windows), which needs Python 3.8+ on PATH. Do not also
install the full plugin from that repo's marketplace, or the skills load twice.

**First run on a fresh machine: a backend needs setting up, and say so before delegating
rather than after a failure.** Nothing is configured out of the box. Point the user at
[GETTING-STARTED.md](https://github.com/aayushpokhrel1/delegation-pipeline/blob/master/GETTING-STARTED.md)
and recommend in this order:

- **`free` + `deepseek` is the intended setup**, and what to describe as the destination:
  `free` runs at $0 and escalates to `deepseek` by itself when it is dry, so the bulk costs
  nothing and the hard cases still land. The escalation needs no configuration beyond having
  both tiers.
- **Start with `deepseek` alone**, because it is the half that works immediately and the
  half that makes the tool worth using: ~Sonnet-class, several times faster than any free
  tier (28s against 186s on the same measured task), and at ~$0.28/Mtok about $5 of prepaid
  credit lasts a long time. Key at https://platform.deepseek.com, env `DEEPSEEK_API_KEY`.
- **Add `free` second, not first.** It is the default backend and the cheapest at volume,
  but it is a LOCAL OmniRoute gateway, so it means Node, `npm i -g omniroute`, a gateway key
  of its own, free-tier provider keys in its dashboard, and autostart. Never a first-run
  step. Do not confuse it with the `openrouter` backend: the names are one letter apart and
  `free`'s model ids read `openrouter/...` because OmniRoute routes through it.
- **Only if the user will not spend anything**: `openrouter` ($0, one key, no local setup,
  but ~50 requests/day and a run spends 3-17 of them) or `nvidia` ($0 trial credits,
  stronger models, churning catalog so `--list-models` first).

Until `free` itself is running, add `"default_backend": "<name>"` to
`~/.claude/delegate.config.json` so the no-backend form below aims at the tier they actually
have, instead of spending three connection failures on an absent local gateway. Once the
gateway is up, drop that line: `free` is the built-in default.
See the [README](https://github.com/aayushpokhrel1/delegation-pipeline) for backends and keys.

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

The backend is optional and defaults to `free`, or to whatever `default_backend` names in
`~/.claude/delegate.config.json`. On failure it tries the tier's spare model
ids (`models` in the backend's config) and then escalates once to `deepseek`.
Every attempt lands in the ledger, the failed one with `"ok": false` and `"escalated_to"`, so
a dry tier leaves a trace instead of looking like a tier nobody routed to.

**After an escalation the tree is clean, so review the diff normally.** A backend that dies
mid-run has its edits rolled back before the fallback starts, so you are never reading half
of one attempt plus all of another. The exception announces itself: if the rollback could not
finish, the run stops without escalating and names the files it could not restore, and that
is the one case where you inspect the tree by hand before doing anything else.

**Give the run a long foreground timeout: up to 600000ms (10 min) on the Bash tool.** The
free tier costs nothing but is slow, and it is now the default, so this applies to every
delegation rather than only the ones that opt in. Measured on one small annotation task
(2026-10-02): `free` took **186s over 9 calls**, `deepseek` took **28s over 3** for the same
work. A `free` failure now walks the tier's spare model ids before escalating, each spending
~25s on its own retries, so the worst case is roughly 25s per configured `free` model plus
the deepseek run. Budget minutes, not seconds, and do not kill a run that looks
stuck. If you need the answer *now* rather than for $0, name `deepseek` explicitly: that is
what naming a backend is for.

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
