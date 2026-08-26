---
description: Hand a mechanical task to a free/cheap model worker, then review its diff
argument-hint: <free|deepseek|kimi> <task description>
allowed-tools: Bash(~/.claude/bin/delegate:*), Bash(git diff:*), Bash(git status:*), Bash(git stash:*), Read, Edit
---

You are the orchestrator. Offload the task below to a cheap/free headless worker via the
`delegate` tool, then review its work. The goal is to spend as little of the paid session's
usage as possible on the grunt work itself.

Arguments: `$ARGUMENTS`

The first whitespace-delimited token is the **backend** (`free`, `deepseek`, or `kimi`);
everything after it is the **task**. If no backend is given, default to `free`.

Follow this protocol:

1. **Check the tree is clean-ish.** Run `git status --short`. If there are unrelated
   uncommitted changes, note them so the worker's diff stays attributable (offer to stash,
   don't stash without asking).
2. **Write a tight spec.** The worker has zero conversation context, so expand the task
   into a self-contained instruction: name the exact files, describe the change precisely,
   and point at a pattern to mirror if one exists. Do this reasoning yourself, cheaply.
3. **Run the worker:**
   ```
   ~/.claude/bin/delegate <backend> "<your expanded self-contained instruction>"
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
