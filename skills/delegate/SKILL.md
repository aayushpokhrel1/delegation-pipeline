---
name: delegate
description: "Use when a coding request contains work you can write a tight spec for and verify from a diff, routed by complexity: trivial/mechanical work (boilerplate, scaffolding, repetitive edits, test stubs, docstrings) to a free worker, and SUBSTANTIAL well-specified work (a whole module, a real multi-file refactor, a non-trivial first-draft implementation, a clear-spec bug fix) to deepseek, which is roughly Sonnet-class. Offloads it to a headless worker via the delegate CLI, then reviews the git diff. The gate is a good spec, not low difficulty. Keeps design, tricky debugging, security-sensitive code, deep-context work, and one-liners in-session."
---

# delegate

Hand work to a cheap or free model worker so the paid Claude session spends its usage on
thinking, not typing. Not just mechanical work: route by complexity, free for trivial edits
and `deepseek` (roughly Sonnet-class) for substantial, well-specified builds. The worker
(`~/.claude/bin/delegate`) is a zero-dependency
Python agent over any OpenAI-compatible endpoint. It can read, search, and edit files in the
current repo. It **cannot** run shell or git, by design: you review the resulting `git diff`
and commit.

Requires the CLI installed once (`bash install.sh` or `./install.ps1` from the repo). See
the [README](https://github.com/aayushpokhrel1/delegation-pipeline) for backends and keys.

## When to use

The gate is whether you can write a tight, verifiable spec, NOT how hard the task is.
Route by complexity:

- **`free`** (weak, $0) for trivial / mechanical work: boilerplate, scaffolding, repetitive
  edits across files, test stubs, docstrings/comments, one-file transcription.
- **`deepseek`** (cheap, roughly Sonnet-class for coding) for SUBSTANTIAL but well-specified
  work: a whole module or component from a clear contract, a real multi-file refactor, a
  non-trivial first-draft implementation, a clear-spec bug fix. Do not cap delegation at
  boilerplate, if you can specify it precisely, deepseek can build it.

Keep in-session: architecture and design, writing the precise spec for each delegated task,
reviewing worker output, tricky debugging, security-sensitive code, deep-context work that
can't be specified in isolation, one-liners (the spec would cost more tokens than the edit).

## How to run

```
~/.claude/bin/delegate <backend> [--model <id>] "<task>"
```

Backends: `free` (OmniRoute, $0), `nvidia` (free trial credits, strong tool-calling models),
`deepseek` (cheap, ~Sonnet-class), `kimi` (premium, only if asked). You are the router: pick
by task COMPLEXITY, `free` for trivial/mechanical, `deepseek` for substantial well-specified
work; `nvidia` when free is dry (tool-calling models only, run `--list-models` and see
`MODELS.md`).

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
