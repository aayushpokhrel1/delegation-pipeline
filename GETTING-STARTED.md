# Getting started (Windows, from nothing)

For someone who has Claude Code installed and nothing else. About 10 minutes, and the
tool itself can stay at $0 forever if you want it to.

**What this does.** It gives Claude a cheap or free second model to hand grunt work to.
You keep talking to Claude; Claude writes the spec, a free model does the typing, Claude
reviews the diff. Your Claude usage goes to the thinking instead of to boilerplate.

Most of the steps below are things you can ask Claude Code to do for you. The two it
cannot do are installing Python and clicking "create key" in a browser.

---

## Step 0: Python 3

The plugin is a single Python script with no dependencies, but Python has to exist. Check
in PowerShell:

```powershell
py -V
```

If that prints `Python 3.x`, skip ahead. If it opens the Microsoft Store or errors, install
it:

```powershell
winget install Python.Python.3.12
```

If you install from [python.org](https://www.python.org/downloads/) instead, tick **"Add
python.exe to PATH"** on the first screen. Close and reopen your terminal afterwards.

Nothing else is needed. No Node, no npm, no Docker, no gateway. (Those are only for the
optional heavy-volume setup at the bottom.)

## Step 1: install the plugin

In Claude Code:

```
/plugin marketplace add aayushpokhrel1/delegation-pipeline
```

```
/plugin install delegation-pipeline
```

Then **start a new Claude Code session**. On session start the plugin writes the worker
launcher to `~/.claude/bin/delegate`. That is the whole install: the commands, the skills
and the worker all ship in the plugin.

Check it landed, in the new session:

```
ls ~/.claude/bin/delegate
```

If the file is not there, Python was not on PATH when the session started. Redo step 0 and
restart the session.

## Step 2: pick a backend

A backend is just the model that does the work. The plugin ships with four configured and
**none of them has a key yet**, so your first delegation will fail until you do this step.

| Backend | Cost | Setup | Good for |
| --- | --- | --- | --- |
| **openrouter** | $0 | One key, 2 minutes | Starting out. Free `:free` models |
| **nvidia** | $0 (trial credits) | One key, 2 minutes | More headroom than OpenRouter, stronger models |
| **deepseek** | ~$0.28 per million tokens | One key plus a top-up | Real work. This is the one that just works |
| **free** (OmniRoute) | $0 | Node, a local gateway, provider keys | High volume, later |

**Start with openrouter.** One key, no local server, genuinely $0.

Its one catch is the quota: about **50 requests a day** on the free tier, and a single
delegation spends between 3 and 17 of them (one per step the worker takes). So expect a
handful of real delegations per day, not dozens. With about $10 of credit on the account
that same free tier goes to roughly 1000 requests a day.

**When you want it to stop being fiddly, put $5 on DeepSeek.** It is not free, but $5 goes
a long way at $0.28 per million tokens, it is roughly Sonnet-class, and it is several times
faster than the free tiers (measured on the same small task: 28 seconds on deepseek against
186 seconds on the free tier). Most people end up here for anything they actually care
about. Free is for grinding, deepseek is for getting on with it.

## Step 3: get the key

- **OpenRouter**: sign in at <https://openrouter.ai/keys>, "Create key", copy it. Starts
  with `sk-or-`.
- **NVIDIA**: <https://build.nvidia.com>, open any model page, "Get API Key". Starts with
  `nvapi-`.
- **DeepSeek**: <https://platform.deepseek.com>, API keys, create one, then add credit
  under Top up. Starts with `sk-`.

A key is a password. Do not paste it into a chat, a commit, or a GitHub issue.

## Step 4: configure it (one small file)

Create `C:\Users\<you>\.claude\delegate.config.json` with exactly this, substituting your
key:

```json
{
  "default_backend": "openrouter",
  "backends": {
    "openrouter": { "api_key": "sk-or-your-key-here" }
  }
}
```

That is the whole configuration. Everything else (endpoints, models, timeouts) already has
a default; this file only overrides what you name.

`default_backend` is the line that matters. Claude is told to delegate **without** naming a
backend, and the built-in default is the local gateway from the bottom of this page. Without
this line every delegation would spend three connection failures on a gateway you never
installed, then give up. With it, a bare `delegate "<task>"` goes straight to your tier.

For deepseek or nvidia instead, swap both the name and the block:

```json
{
  "default_backend": "deepseek",
  "backends": {
    "deepseek": { "api_key": "sk-your-key-here" }
  }
}
```

You can configure several and switch the default whenever. Environment variables
(`OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`) work too, but on Windows
`setx` only applies to terminals opened afterwards, which quietly bites you, so the file is
the easier path.

Or just ask Claude Code, in the folder you want to work in:

> Set up the delegation pipeline to use OpenRouter as the default backend. My key is in my
> clipboard, tell me where to paste it.

The file is never committed and it is not inside any repo.

## Step 5: prove it works

In any git repository, ask Claude:

> Delegate this to the pipeline: add a one-line docstring to every function in
> `<some file>` that lacks one. Then show me the diff.

What you should see: Claude announces the backend in one line, the worker runs for anywhere
from 20 seconds to a few minutes, and it prints a `SUMMARY:` and a `TOKENS:` line. Then
Claude reviews the `git diff` with you.

To run it yourself without Claude, from PowerShell:

```powershell
& "$HOME\.claude\bin\delegate.cmd" "summarize what this project does in 3 bullets"
```

**Be patient on the free tier.** A free run that takes three minutes is normal, not stuck.
If you need the answer now rather than for $0, name deepseek explicitly.

## Step 6: using it day to day

You mostly do not have to do anything. The plugin tells Claude to delegate on its own
whenever a task is specifiable and checkable from a diff, so you just work normally and
Claude offloads the grinding. Claude announces each handoff in one line and reviews the
diff with you afterwards.

When you want to be explicit:

| | |
| --- | --- |
| `/delegate <task>` | Hand one task to the worker, review the diff |
| `/orchestrate` | Drive a multi-task plan, routing each task and committing per task |
| "don't delegate this" | Keeps everything in-session for that conversation |

Two things never get delegated, by design: the worker cannot run shell commands and cannot
use git. It only reads, searches and edits files in the current repository. You and Claude
run the tests and make the commits.

And know what you are agreeing to: delegating sends the task text plus the contents of any
file the worker reads to whichever provider you configured. For a private or sensitive
repository, say "don't delegate this". [PRIVACY.md](PRIVACY.md) spells out exactly what
leaves the machine.

## Step 7: see what it saved you

```powershell
& "$HOME\.claude\bin\delegate.cmd" --stats
```

Tokens offloaded, what you paid on the worker tier, and an estimate of the Claude tokens
you avoided. It reads a local ledger at `~/.claude/delegate-usage.jsonl` that never leaves
your machine. It also warns you when a backend has been failing recently, which is the
thing you would otherwise never notice.

---

## When something goes wrong

| What you see | What it means |
| --- | --- |
| No `~/.claude/bin/delegate` | Python was not on PATH at session start. Step 0, then restart the session |
| `No backend is set up yet` plus a list of options | You have not done step 4, or the key is wrong. That message is a short version of this page |
| `401` / `invalid_api_key` | Wrong key, or pasted into the wrong backend's block |
| `429` / `insufficient_quota` | You hit the free tier's daily cap. Wait, add credit, or switch `default_backend` to deepseek |
| It ran for minutes and died | Normal for a free tier under load. Re-run, or name deepseek |
| `Unknown backend '<your whole task>'` | A stale worker. Reinstall the plugin |
| `default_backend '<name>' is not a configured backend` | Typo in step 4, or the name does not match the block below it |

Claude Code can read any of these errors and fix them with you. Paste it in and ask.

## Later: the `free` / OmniRoute tier

Only worth it when you are delegating constantly and the free remote quotas are getting in
your way. It runs a local gateway that fans out across many providers' free tiers, so the
ceiling is much higher, but it is a real setup: Node, `npm i -g omniroute`, a key the
gateway issues to itself, free-tier keys from Groq, Cerebras and Gemini added in its
dashboard, and a scheduled task to keep it running. The
[README](README.md#autostart) has all of it, including the Windows autostart script.

Do not start there. Get the $0 remote tier working first, use it for a week, and see whether
you ever actually hit the ceiling.
