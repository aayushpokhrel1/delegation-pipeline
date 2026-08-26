---
description: Hand a mechanical task to a free/cheap model worker, then review its diff
argument-hint: [free|nvidia|deepseek|kimi] <task description>
allowed-tools: Bash(~/.claude/bin/delegate:*), Bash(git diff:*), Bash(git status:*), Bash(git stash:*), Read, Edit
---

You are the orchestrator. Offload the task below to a cheap/free headless worker via the
`delegate` tool, then review its work. The goal is to spend as little of the paid session's
usage as possible on the grunt work itself.

Arguments: `$ARGUMENTS`

If the first whitespace-delimited token is a known backend (`free`, `nvidia`, `deepseek`,
`kimi`), use it and treat the rest as the **task**. Otherwise treat the whole thing as the
task and **you choose the backend and model yourself** based on the task.

**You are the router.** Size up the task and pick:
- **Backend:** `free` (OmniRoute, $0) when its pool is healthy; `nvidia` (free trial
  credits, strong tool-calling models) when free is dry; `deepseek` for
  reliability-sensitive or trickier work; `kimi` only if the user asked.
- **Model (mainly for `nvidia`):** pass `--model <id>` matched to the task. Read
  `MODELS.md` in this repo for the task->model shortlist, and run
  `~/.claude/bin/delegate <backend> --list-models` to see the live catalog. Only pick
  tool-calling-capable models (the worker edits via function calls); when unsure, use the
  backend default. Verified `nvidia` picks: `deepseek-ai/deepseek-v4-flash-0731` (default,
  fast/cheap), `nvidia/nemotron-3-super-120b-a12b` (quality), `nvidia/nemotron-3-nano-30b-a3b`
  (small). The catalog changes, so `--list-models` if a pick 404s or 410s.

State which backend and model you chose and why in one line before running.

Follow this protocol:

1. **Check the tree is clean-ish.** Run `git status --short`. If there are unrelated
   uncommitted changes, note them so the worker's diff stays attributable (offer to stash,
   don't stash without asking).
2. **Write a tight spec.** The worker has zero conversation context, so expand the task
   into a self-contained instruction: name the exact files, describe the change precisely,
   and point at a pattern to mirror if one exists. Do this reasoning yourself, cheaply.
3. **Run the worker** with your chosen backend and (optionally) model:
   ```
   ~/.claude/bin/delegate <backend> [--model <id>] "<your expanded self-contained instruction>"
   ```
   Its step logs go to stderr and its summary to stdout.
4. **Review.** Run `git diff` and actually read the changes. The worker cannot run shell,
   tests, or git, so verify correctness yourself. Fix small issues inline with Edit;
   re-delegate with a sharper spec if it drifted badly.
5. **Report** what changed, what you corrected, and anything the user should verify or that
   still needs tests run / a commit (you don't commit unless asked).

Do NOT delegate design decisions, tricky debugging, or security-sensitive code: handle
those in-session. If `delegate` errors that a backend needs a key or that OmniRoute isn't
running (for `free`), relay the fix instead of retrying blindly.
