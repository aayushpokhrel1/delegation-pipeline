---
name: delegate
description: "Use when a coding request contains token-heavy grunt work (boilerplate, scaffolding, mechanical refactors, repetitive edits across files, first-draft implementations, test stubs, docstrings/comments, straightforward bug fixes with a clear spec). Offloads that work to a free/cheap headless worker model via the delegate CLI, then reviews the worker's git diff. Keeps design, tricky debugging, security-sensitive code, and one-liners in-session."
---

# delegate

Hand mechanical work to a cheap or free model worker so the paid Claude session spends its
usage on thinking, not typing. The worker (`~/.claude/bin/delegate`) is a zero-dependency
Python agent over any OpenAI-compatible endpoint. It can read, search, and edit files in the
current repo. It **cannot** run shell or git, by design: you review the resulting `git diff`
and commit.

Requires the CLI installed once (`bash install.sh` or `./install.ps1` from the repo). See
the [README](https://github.com/aayushpokhrel1/delegation-pipeline) for backends and keys.

## When to use

Delegate: boilerplate, scaffolding, mechanical refactors, repetitive edits across files,
first-draft implementations, test stubs, docstrings/comments, straightforward bug fixes with
a clear spec.

Keep in-session: architecture and design, writing the precise spec for each delegated task,
reviewing worker output, tricky debugging, security-sensitive code, one-liners (the spec
would cost more tokens than the edit).

## How to run

```
~/.claude/bin/delegate <backend> [--model <id>] "<task>"
```

Backends: `free` (OmniRoute, $0), `nvidia` (free trial credits, strong tool-calling models),
`deepseek` (cheap, reliable), `kimi` (premium, only if asked). You are the router: prefer
`free`; use `nvidia` when free is dry (tool-calling models only, run `--list-models` and see
`MODELS.md`); use `deepseek` for reliability-sensitive work.

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
