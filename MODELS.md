# Choosing a model (orchestrator cheat-sheet)

`delegate.py` never picks a model on its own beyond the per-backend default. The
**orchestrator** (Opus) chooses: first the backend, then, for `nvidia`, the model,
matched to the task. Pass it with `--model`.

## The worker needs tool calling

The delegate loop drives everything through OpenAI function-calling (`read_file`,
`edit_file`, ...). **Only pick models that support tool calling.** Pure reasoning
models (e.g. `deepseek-ai/deepseek-r1`) often ignore the `tools` API and will spin
without editing, so avoid them for edit tasks. When unsure, fall back to the default.

## NVIDIA backend: task -> model

**Always verify with `delegate nvidia --list-models` first, the catalog changes often.**
Models reach end-of-life on a date and then return `HTTP 410 Gone` (e.g.
`meta/llama-3.3-70b-instruct` EOL'd 2026-08-26), and some catalog ids return
`HTTP 404 "not found for account"` because they aren't enabled for your key. The tool
surfaces these errors clearly, just pick another id and retry.

Verified working (tool-calling drives the edit loop) as of 2026-08-26:

| Task shape                                | Model (`--model ...`)                  | Notes                        |
|-------------------------------------------|----------------------------------------|------------------------------|
| **Default / fast** (cheap, clean, 3 steps)| `deepseek-ai/deepseek-v4-flash-0731`   | backend default; great pick  |
| **Highest quality**                       | `nvidia/nemotron-3-super-120b-a12b`     | strong, more credits         |
| **Small / cheap** bulk                    | `nvidia/nemotron-3-nano-30b-a3b`        | works, less efficient        |

Do NOT rely on the older `meta/llama-*`, `qwen*`, `mistralai/*-instruct` ids from earlier
NVIDIA docs, on this account they 404 or have EOL'd. Confirm any new pick with a one-file
smoke test before a big run.

## Which backend first

1. `free` (OmniRoute) when its pool is healthy: $0, no credits burned.
2. `nvidia` when free is dry: free trial credits, strong tool-calling models.
3. `deepseek` for reliability-sensitive or trickier work: cheap and dependable.
4. `kimi` only when explicitly asked: premium.

## How Opus should decide

For each delegated task, Opus (cheaply, in-session) sizes it up:
- Trivial/mechanical + huge volume -> cheapest tool-capable model (`free`, or
  `nvidia --model meta/llama-3.1-8b-instruct`).
- Code-shaped -> a coder model (`qwen2.5-coder`) or the 70B default.
- Needs care but not paid-tier -> `nvidia` 70B / Nemotron.
- Reliability critical -> `deepseek`.

Then it writes the tight spec, runs the worker, and reviews the diff as usual.
