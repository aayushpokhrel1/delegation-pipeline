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

Live list any time: `delegate nvidia --list-models`. Sensible picks:

| Task shape                                   | Model (`--model ...`)                     | Tools |
|----------------------------------------------|-------------------------------------------|-------|
| **Default / general edits** (safe pick)      | `meta/llama-3.3-70b-instruct`             | yes   |
| **Code-heavy** refactors, generation         | `qwen/qwen2.5-coder-32b-instruct`         | yes   |
| **Cheap / fast / trivial** bulk edits        | `meta/llama-3.1-8b-instruct`              | yes   |
| **Bigger reasoning, still tool-capable**     | `nvidia/llama-3.1-nemotron-70b-instruct`  | yes   |
| **Highest quality** (slow, credit-hungry)    | `meta/llama-3.1-405b-instruct`            | yes   |

(Model ids come from the catalog and can change; verify with `--list-models`. The `yes`
column is the expected default; confirm with a one-file smoke test before a big run.)

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
