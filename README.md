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

| Backend    | Provider              | Cost         | Notes                                    |
|------------|-----------------------|--------------|------------------------------------------|
| `free`     | OmniRoute (local)     | $0           | Local gateway, `auto/coding` model       |
| `nvidia`   | NVIDIA API Catalog    | free credits | build.nvidia.com; strong models, free tier |
| `deepseek` | DeepSeek API          | cheap        | Reliable; good default for real work     |
| `kimi`     | Kimi / Moonshot API   | premium      | Strongest; use when quality matters      |

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
- **nvidia**: get a free key at https://build.nvidia.com (any model page → "Get API Key",
  it starts with `nvapi-`), then:
  ```bash
  export NVIDIA_API_KEY=nvapi-...
  ```
  The `nvidia` backend is OpenAI-compatible via `https://integrate.api.nvidia.com/v1`.
  It defaults to `meta/llama-3.3-70b-instruct` (supports the tool-calling the worker needs);
  override per run with `--model`, e.g. `--model deepseek-ai/deepseek-r1` or a Nemotron/Qwen
  id from the catalog. This is a great **free** path when OmniRoute's keyless routes are dry.

  You can also plug NVIDIA into OmniRoute itself (so the `free`/`auto` router can use it):
  open `http://localhost:20128` → provider keys → add the NVIDIA key. Either way works;
  the direct `nvidia` backend is the more predictable of the two.

### Autostart

So you never have to start the gateway by hand. Logs land in `~/.claude/omniroute.log`,
and every installer prefers a global `omniroute` (`npm i -g omniroute`) and falls back to
`npx --yes omniroute`.

**Windows** (Scheduled Task, launches hidden at logon):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
Start-ScheduledTask -TaskName "OmniRoute Gateway"                 # start now, no reboot
powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1   # remove
```

**macOS** (launchd agent, `RunAtLoad` + `KeepAlive` so it restarts if it dies):
```bash
bash scripts/install-autostart.sh          # starts immediately and at every login
bash scripts/uninstall-autostart.sh        # remove
```

**Linux** (systemd `--user` service, restarts on failure):
```bash
bash scripts/install-autostart.sh          # enable + start now, and at every login
sudo loginctl enable-linger "$USER"        # optional: keep running without an active login
bash scripts/uninstall-autostart.sh        # remove
```

All installers are idempotent, they won't start a second copy if one is already running.
For a one-off manual start on macOS/Linux without installing autostart, use
`bash scripts/start-omniroute.sh`.

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

Flags: `--dir <path>` (repo root, default cwd), `--model <id>` (override),
`--max-steps N`, `--list-models` (print the backend's catalog and exit).

### Letting Claude pick the model

The tool never auto-selects a model beyond each backend's default, that's the
orchestrator's job. When you run `/delegate` (or Opus drives the raw CLI), Claude sizes up
the task and chooses the backend and, for `nvidia`, the `--model`, using `--list-models`
to see the live catalog and [`MODELS.md`](MODELS.md) as the task->model shortlist. Only
tool-calling-capable models are picked, since the worker edits via function calls. You can
still force a specific backend/model by naming them.

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

### Proactive delegation (no `/delegate` needed)

The orchestrator (Opus) is set up to delegate **on its own** whenever a request contains
qualifying grunt work, without you typing `/delegate`. It announces the backend/model in
one line, runs the worker, reviews the diff, and folds the result in. `/delegate` and
saying "delegate this" still work as manual triggers; they're just not required. Say
**"don't delegate this"** to keep a task (or a sensitive repo) in-session.

Note: delegating sends repo content to external model providers (`deepseek`/`nvidia` are
remote; `free`/OmniRoute routes out too). That's the intended trade; disable it per-repo
when the code is sensitive.

This behavior lives in your **global `~/.claude/CLAUDE.md`**, not in this repo, so it
travels with that file, not with a clone. To enable it on another device, add a block like
this to that device's `~/.claude/CLAUDE.md`:

```markdown
# Delegation to cheap-model workers
Use `~/.claude/bin/delegate <backend> [--model <id>] "<task>"` to offload grunt work.
Delegate proactively (no /delegate needed): announce the backend/model in one line, run
the worker, then review the git diff. You route: prefer `free`, use `nvidia` when free is
dry (tool-calling models only, see MODELS.md), `deepseek` for reliability-sensitive work.
Keep design, tricky debugging, security-sensitive code, and one-liners in-session. Stop if
told "don't delegate this".
```

(The full version is in this repo's git history / the author's own CLAUDE.md.)

## Tools the worker has

`list_dir`, `find_files`, `read_file`, `search_text`, `write_file`, `edit_file`.
No shell, no network beyond the model endpoint, no git. File access is sandboxed to the
working directory.

## Portability

Everything the worker needs is one `delegate.py` file and the stdlib, so it runs on any
device with Python 3.8+. Sync = clone this repo + run the installer. Real keys live in
`~/.claude/delegate.config.json` (git-ignored), never in the repo.
