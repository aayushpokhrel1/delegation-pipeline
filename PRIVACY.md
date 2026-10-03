# Privacy policy

**Delegation Pipeline** is a command-line tool that runs entirely on your machine. There is
no service behind it, no account, and no server operated by its author. Nothing in this
project reports to the author, and the author receives no data about you or your use of it.

Last updated: 2026-10-02. This policy covers the `delegation-pipeline` plugin and the
`delegate` worker it ships.

## What the author collects

Nothing. There is no telemetry, no analytics, no crash reporting, no license check, and no
update ping. The project has no server to collect anything with.

## What leaves your machine, and where it goes

The tool's purpose is to send a coding task to a language model that you choose. When you run
a delegation, it sends to **the backend you configured**, and only to that backend:

- the task description you (or Claude, on your instruction) wrote, and
- the contents of files it reads or edits inside the repository you ran it in.

The destination is whichever OpenAI-compatible endpoint your configuration names. The
defaults ship in [`config.example.json`](config.example.json) and you can change any of them
in `~/.claude/delegate.config.json`:

| Backend | Endpoint | Operated by |
| --- | --- | --- |
| `free` | `http://localhost:20128/v1` | An OmniRoute gateway you run. It is a router, so it forwards your request to an upstream provider |
| `deepseek` | `api.deepseek.com` | DeepSeek |
| `kimi` | `api.moonshot.ai` | Moonshot |
| `nvidia` | `integrate.api.nvidia.com` | NVIDIA |
| `openrouter` | `openrouter.ai` | OpenRouter, which forwards to the model's provider |

**Once your data reaches one of those providers, that provider's privacy policy governs it,
not this one.** What they retain, whether they train on it, and for how long are their terms
to state and yours to check. This project has no control over and no visibility into any of it.

One further outbound request exists: if you pass `--image <url>`, or the worker model calls
its `view_image` tool with a URL, the tool issues a plain `GET` to that URL. It sends no
credentials and no repository content, only a `User-Agent`. The image it fetches is then sent
to your chosen backend as part of the request.

## Credentials

API keys are read from the environment variables named in your configuration
(`DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `MOONSHOT_API_KEY`), or from an
`api_key` value you place in `~/.claude/delegate.config.json`.

Each key is sent only to the provider it belongs to, as that provider's `Authorization`
header. Keys are never logged, never written to the usage ledger described below, never sent
to the author, and never sent to any host other than the one they authenticate.

## What is stored on your machine

Two files, both under `~/.claude/`, both local and never transmitted:

- **`~/.claude/delegate.config.json`** holds your backend configuration, including any API key
  you choose to put there rather than in your environment.
- **`~/.claude/delegate-usage.jsonl`** is a usage ledger with one line per run: timestamp,
  backend, model, token counts, elapsed time, the repository's **directory name** (not its
  path and not its contents), and whether verify and commit succeeded. It exists so
  `delegate --stats` can show you what you have spent. Delete the file at any time to clear
  it; it is recreated on the next run.

The plugin also writes `~/.claude/bin/delegate`, a launcher script, at the start of a Claude
Code session.

## What the tool will not do

The worker model can read, search, and edit files inside the repository you invoke it in. It
**cannot** run shell commands, use git, or read or write anything outside that directory. The
`--verify` and `--commit` flags are executed by the command-line harness on your instruction,
never by the model.

## Children

This project is a developer tool and is not directed at children under 13, or under 16 where
that is the applicable age. It collects no personal information from anyone.

## Your choices

Delegation never happens on its own. Every run is started by you, or by Claude acting on an
instruction you gave it. To send nothing anywhere, do not run `delegate`. To keep a specific
repository out of it, do not delegate in that repository, or tell Claude not to. To keep your
data off third-party servers entirely, point the `free` backend at a model you host yourself:
any OpenAI-compatible endpoint works.

## Changes

Changes to this policy are made in this file, in a public repository, with full history. The
"last updated" date above records the most recent one.

## Contact

Open an issue at
<https://github.com/aayushpokhrel1/delegation-pipeline/issues>.
