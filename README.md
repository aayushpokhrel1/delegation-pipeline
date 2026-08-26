# Delegation Pipeline

Offload token-heavy grunt work from your paid Claude Code session to **free or cheap
models**, so your Claude usage goes to the thinking, not the typing.

`delegate` is a zero-dependency Python worker (stdlib only) that runs a small agentic
loop over any **OpenAI-compatible** endpoint. It can read, search, and edit files in the
current repo. It **cannot** run shell commands or use git, by design: you (or your Claude
orchestrator) review the resulting `git diff` and commit.

```
~/.claude/bin/delegate <backend> "<task>"
```

## Backends

| Backend    | Provider              | Cost    | Notes                                    |
|------------|-----------------------|---------|------------------------------------------|
| `free`     | OmniRoute (local)     | $0      | Local gateway, `auto/coding` model       |
| `deepseek` | DeepSeek API          | cheap   | Reliable; good default for real work     |
| `kimi`     | Kimi / Moonshot API   | premium | Strongest; use when quality matters      |

All three are just an OpenAI-compatible base URL + model + key, configured in
`~/.claude/delegate.config.json`.

## Install

Clone this repo anywhere, then run the installer for your OS:

```bash
bash install.sh
```

```powershell
./install.ps1
```

This writes a `delegate` launcher into `~/.claude/bin/` (pointing at your checkout) and
seeds `~/.claude/delegate.config.json` from the example. Re-run after moving the repo.

### Keys

- **free**: no key. Just run OmniRoute in another terminal:
  ```bash
  npx omniroute      # serves http://localhost:20128/v1
  ```
  Or have it start automatically at every logon (Windows), see
  [Autostart](#autostart-windows) below.
- **deepseek / kimi**: set env vars, or paste the key into `delegate.config.json`
  (that file is git-ignored):
  ```bash
  export DEEPSEEK_API_KEY=sk-...
  export MOONSHOT_API_KEY=sk-...
  ```

### Autostart (Windows)

So you never have to start the gateway by hand:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
```

This registers a Scheduled Task ("OmniRoute Gateway") that launches OmniRoute hidden at
every logon (15s delay so the network is up). It's idempotent, it won't start a second
copy if one is already running. Manage it:

```powershell
Start-ScheduledTask -TaskName "OmniRoute Gateway"                 # start now, no reboot
powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1   # remove
```

Logs land in `~/.claude/omniroute.log`. The launcher prefers a global `omniroute`
(`npm i -g omniroute`) and falls back to `npx --yes omniroute`.

### Widening the free pool (recommended)

OmniRoute ships with only a couple of keyless free providers (OpenCode Zen, Felo). Their
shared quota is frequently exhausted (`403 insufficient_quota` / `429`), which makes the
bare `free` backend unreliable. Add your own **free-tier** API keys so the router has
healthy routes to fall back to. All of these give a free key at signup:

| Provider          | Free tier                    | Get a key                         |
|-------------------|------------------------------|-----------------------------------|
| **Groq**          | Fast, generous free tier     | https://console.groq.com/keys     |
| **Cerebras**      | ~1M tokens/day free          | https://cloud.cerebras.ai         |
| **Google Gemini** | Free tier (Flash models)     | https://aistudio.google.com/apikey |
| **Mistral**       | Free experiment tier         | https://console.mistral.ai        |
| **OpenRouter**    | `:free` models               | https://openrouter.ai/keys        |
| **GitHub Models** | Free (rate-limited)          | GitHub settings → developer token |

Add them in the OmniRoute dashboard (open `http://localhost:20128` → provider/keys page,
keys are encrypted at rest), or via CLI (`omniroute keys`). Groq + Cerebras + Gemini alone
make `free` solidly usable for grunt work. When free is dry, `deepseek` remains the
reliable paid-but-cheap fallback.

## Use it

```bash
# smoke test (needs OmniRoute running)
~/.claude/bin/delegate free "Summarize what this project does in 3 bullets"

# real grunt work
~/.claude/bin/delegate deepseek "Add type hints to every function in src/parser.py"
~/.claude/bin/delegate free "Write a docstring for each exported function in utils/*.js"
```

Step logs stream to **stderr**; the final **summary** prints to **stdout**.

Flags: `--dir <path>` (repo root, default cwd), `--model <id>` (override), `--max-steps N`.

### From inside Claude Code: `/delegate`

The installer also drops a `/delegate` slash command into `~/.claude/commands/`, so you can
trigger a delegation without leaving your Claude session:

```
/delegate deepseek Add type hints to every function in src/parser.py
/delegate free Write a docstring for each exported function in utils/
```

The command has Claude expand your request into a tight, self-contained spec, run the
worker, then review the resulting `git diff` and report back. First token is the backend
(`free` if omitted); the rest is the task.

## How Claude should drive it

The orchestrator protocol lives in your global `~/.claude/CLAUDE.md`. In short:

1. Write a tight, self-contained instruction (name the files, describe the change,
   point at a pattern to mirror). The worker has no conversation context.
2. Delegate on a clean tree so the resulting `git diff` is attributable.
3. **Review** the diff. Fix small issues yourself; re-delegate with a sharper spec if it
   drifted. Workers never commit.
4. You run tests and commit, after review.

Delegate bulk mechanical work (boilerplate, repetitive edits, docstrings, first drafts).
Keep design, tricky debugging, and security-sensitive code in the Claude session.

## Tools the worker has

`list_dir`, `find_files`, `read_file`, `search_text`, `write_file`, `edit_file`.
No shell, no network beyond the model endpoint, no git. File access is sandboxed to the
working directory.

## Portability

Everything the worker needs is one `delegate.py` file and the stdlib, so it runs on any
device with Python 3.8+. Sync = clone this repo + run the installer. Real keys live in
`~/.claude/delegate.config.json` (git-ignored), never in the repo.
