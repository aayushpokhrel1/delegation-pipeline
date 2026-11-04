# Getting started (Windows, from nothing)

For someone who has Claude Code installed and nothing else.

**What this does.** It gives Claude a cheap second model to hand grunt work to. You keep
talking to Claude; Claude writes the spec, the cheap model does the typing, Claude reviews
the diff. Your Claude usage goes to the thinking instead of to boilerplate.

**The short version.** Install Python, install the plugin, put $5 on DeepSeek, paste the
key into one small file. Fifteen minutes, and then it just works. Everything else on this
page is optional.

---

## 1. Python 3

The worker is a single Python script with no dependencies, but Python has to exist. In
PowerShell:

```powershell
py -V
```

Prints `Python 3.x`? Move on. Opens the Microsoft Store or errors?

```powershell
winget install Python.Python.3.12
```

(From [python.org](https://www.python.org/downloads/) instead, tick **"Add python.exe to
PATH"** on the first screen.) Close and reopen your terminal afterwards.

No Node, no Docker, nothing else.

## 2. The plugin

In Claude Code:

```
/plugin marketplace add aayushpokhrel1/delegation-pipeline
```

```
/plugin install delegation-pipeline
```

Then **start a new Claude Code session**. That is the whole install: the commands, the
skills and the worker all ship in the plugin, and a session-start hook writes the worker to
`~/.claude/bin/delegate`. Confirm it in the new session:

```
ls ~/.claude/bin/delegate
```

Missing? Python was not on PATH when the session started. Redo step 1, restart the session.

## 3. DeepSeek, and why it is the answer

A backend is just the model that does the work. Four ship configured and **none has a key
yet**, so your first delegation fails until you do this.

Use **deepseek**. It is not free, but:

- ~$0.28 per million tokens. For scale, this project's own ledger has spent **$24.84 across
  144 deepseek runs** and 88.7M tokens, so **$5 is roughly 25 to 30 real delegations**
- roughly Sonnet-class, which means it can be trusted with a real module or a refactor,
  not just boilerplate
- **several times faster than the free tiers.** Measured on the same small task: 28 seconds
  on deepseek against 186 seconds on free

The free options exist and they work, but they are slow and they run dry under load. If you
are going to use this tool at all, $5 is the difference between a tool you reach for and a
tool you stop reaching for.

Get the key at <https://platform.deepseek.com>: API keys, create one, then add credit under
Top up. It starts with `sk-`. A key is a password; do not paste it into a chat or a commit.

## 4. One small file

Create `C:\Users\<you>\.claude\delegate.config.json`:

```json
{
  "default_backend": "deepseek",
  "backends": {
    "deepseek": { "api_key": "sk-your-key-here" }
  }
}
```

That is the whole configuration. Endpoints, models and timeouts already have defaults; this
file only overrides what you name. It lives outside any repository and is never committed.

`default_backend` is the line that matters: Claude is told to delegate *without* naming a
backend, and the built-in default is the local gateway from step 6 that you have not
installed. This line points the default at what you actually have.

Or just ask Claude Code:

> Set up the delegation pipeline to use DeepSeek as the default backend, and tell me where
> to paste my key.

## 5. Use it

Mostly you do nothing. The plugin tells Claude to delegate on its own whenever a task is
specifiable and checkable from a diff, so you work normally and Claude offloads the
grinding, announcing each handoff in one line and reviewing the diff with you after.

When you want to be explicit:

| | |
| --- | --- |
| `/delegate <task>` | Hand one task over, review the diff |
| `/orchestrate` | Drive a multi-task plan, routing and committing per task |
| "don't delegate this" | Keeps everything in-session for that conversation |

To watch what it saves you:

```powershell
& "$HOME\.claude\bin\delegate.cmd" --stats
```

Two things the worker can never do, by design: run shell commands, or use git. It only
reads, searches and edits files in the current repository. You and Claude run the tests and
make the commits.

Know what you are agreeing to, though: delegating sends the task text plus the contents of
any file the worker reads to whichever provider you configured. For a private or sensitive
repository, say "don't delegate this". [PRIVACY.md](PRIVACY.md) spells out exactly what
leaves the machine.

## 6. Optional: add the free tier on top

**Two similar names, two different things.** The `free` backend is **OmniRoute**, a gateway
you run on your own machine that fans out across many providers' free tiers. `openrouter` is
**OpenRouter**, a remote service you just point at with a key. OmniRoute happens to route
*through* OpenRouter among others, which is why some `free` model ids read
`openrouter/something`. They are not the same backend and they are set up completely
differently.

**`free` plus `deepseek` is the setup this tool is designed around**, and it is worth
reaching once you are delegating a lot. `free` becomes the default and costs nothing, and
when it is dry or slow the run **escalates to deepseek by itself**, so you get $0 for the
bulk of the work and reliability when it matters. That escalation is built in: it needs no
configuration beyond having both tiers.

It is a real setup, which is why it is step 6 and not step 3. You need Node, then
`npm i -g omniroute`, a key the gateway issues to itself, ideally some free-tier provider
keys (Groq, Cerebras, Gemini) added in its dashboard, and a scheduled task to keep it
running. The [README](README.md#autostart) has all of it, including the Windows autostart
script.

Once it is up, delete the `default_backend` line and `free` becomes the default again, with
deepseek behind it.

If you would rather not spend the $5 at all, **openrouter** is the $0 alternative with no
local setup: one key from <https://openrouter.ai/keys>, `"default_backend": "openrouter"`.
Expect about 50 requests a day at $0 and a run spends 3 to 17 of them, so a handful of
delegations per day, slowly.

## When something goes wrong

| What you see | What it means |
| --- | --- |
| No `~/.claude/bin/delegate` | Python was not on PATH at session start. Step 1, then restart the session |
| `No backend is set up yet` plus a list | You have not done step 4, or the key is wrong. That message is a short version of this page |
| `401` / `invalid_api_key` | Wrong key, or pasted into the wrong backend's block |
| `429` / `insufficient_quota` | Out of credit, or a free tier's daily cap |
| A run took minutes and died | Normal on a free tier under load. This is what the $5 buys you |
| `default_backend '<name>' is not a configured backend` | Typo in step 4, or the name does not match the block below it |

Paste any of these into Claude Code and ask. It can read them and fix them with you.
