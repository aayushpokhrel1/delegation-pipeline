# Choosing a model (orchestrator cheat-sheet)

`delegate.py` never picks a model on its own beyond the per-backend default. The
**orchestrator** (Opus) chooses: first the backend, then the model/route via `--model`,
matched to the task. For `free` (OmniRoute) that means an `auto/*` route; for `nvidia`
(and the paid backends) it means a concrete model id.

## The worker needs tool calling

The delegate loop drives everything through OpenAI function-calling (`read_file`,
`edit_file`, ...). **Only pick models that support tool calling.** Pure reasoning
models (e.g. `deepseek-ai/deepseek-r1`) often ignore the `tools` API and will spin
without editing, so avoid them for edit tasks. When unsure, fall back to the default.

## free backend (OmniRoute): task -> route

For `free`, prefer an **`auto/*` router alias** over a concrete model id. The router fails
over across your healthy providers (Groq, Cerebras, Gemini, Mistral, OpenRouter, plus the
keyless defaults), so if one is rate-limited it silently tries the next. Pinning a specific
model id routes to only that one provider, so it fails instead of falling over, use a
concrete id only when you deliberately want that provider.

| Task shape                                  | Route (`--model ...`)   |
|---------------------------------------------|-------------------------|
| **Code edits / refactors** (default)        | `auto/coding`           |
| **Trivial / high-volume** bulk edits        | `auto/cheap`            |
| **Latency-sensitive**, keep it moving       | `auto/fast`             |
| **Force only no-cost routes**               | `auto/coding:free`      |
| **Prefer the most reliable free route**     | `auto/coding:reliable`  |

`delegate free --list-models` shows every route alias and all ~115 concrete model ids. If a
route keeps 403/429-ing, the keyless pool is exhausted, add provider keys in the OmniRoute
dashboard (you have Groq/Cerebras/Gemini/Mistral/OpenRouter) or switch to `nvidia`.

## NVIDIA backend: task -> model

**Always verify with `delegate nvidia --list-models` first, the catalog changes often.**
Models reach end-of-life on a date and then return `HTTP 410 Gone` (e.g.
`meta/llama-3.3-70b-instruct` EOL'd 2026-08-26), and some catalog ids return
`HTTP 404 "not found for account"` because they aren't enabled for your key. The tool
surfaces these errors clearly, just pick another id and retry.

Verified by an end-to-end smoke test (edit -> verify -> commit) as of 2026-09-17:

| Task shape                                | Model (`--model ...`)                  | Notes                                              |
|-------------------------------------------|----------------------------------------|----------------------------------------------------|
| **Default / working** (verified today)    | `nvidia/nemotron-3-super-120b-a12b`    | current backend default; edits and tool-calls cleanly |
| **Do NOT use** (hangs)                    | `deepseek-ai/deepseek-v4-flash-0731`   | in the catalog and key is valid, but the chat call never returns (stalled 4+ min, zero steps). Was the old default. |
| **EOL, returns HTTP 410**                 | `nvidia/nemotron-3-nano-30b-a3b`       | reached end of life 2026-09-01                     |

The old default (`deepseek-ai/deepseek-v4-flash-0731`) hung on this account, so the backend
default is now `nvidia/nemotron-3-super-120b-a12b`. Do NOT rely on the older `meta/llama-*`,
`qwen*`, `mistralai/*-instruct` ids from earlier NVIDIA docs either, on this account they 404
or have EOL'd. The catalog churns fast, so **always `--list-models` first** and confirm any
new pick with a one-file smoke test before a big run.

## OpenRouter backend: task -> model

OpenAI-compatible at `https://openrouter.ai/api/v1`, auth `Bearer $OPENROUTER_API_KEY`.
Same rule as NVIDIA: **the worker drives tools, so pick tool-capable models only**, and the
catalog churns, so **`delegate openrouter --list-models` first**.

Free models carry a **`:free` suffix** (`$0` prompt + completion). As of the 2026-09-17
survey, OpenRouter listed 444 models: 24 free, 14 of those also vision (image input).

| Task shape                                   | Model (`--model ...`)                | Notes                                    |
|----------------------------------------------|--------------------------------------|------------------------------------------|
| **Default / fast free** (backend default)    | `nvidia/nemotron-3.5-lightning:free` | tool-capable, fast; picked from the survey (confirm with a local smoke test once your key is set) |
| **Free, tool-capable alternates**            | `inclusionai/ling-3.0-flash-*:free`, `poolside/laguna-xs-2.1:free` |                                          |
| **Free, tiny/fastest**                       | `liquid/lfm-2.5-2.6b:free`           | smallest; for trivial bulk edits         |
| **Free vision** (image input)                | `google/gemma-4-31b-it:free`, `inclusionai/ling-3.0-flash-vl:free`, `thinkingmachines/inkling:free` | the worker is text-only today; useful if you extend it |

**Free-tier rate limits:** ~50 requests/day at a `$0` balance, ~1000/day with ~$10 of
credits on the account. Some free models also require enabling prompt-logging/training in
your OpenRouter **privacy settings** or they reject the request with a data-policy error, so
if a `:free` id 4xxs on a policy message, either flip that setting or pick another id.

Note the overlap: OmniRoute (`free`) already routes *through* OpenRouter among its providers.
A direct `openrouter` backend is worth it when you want **explicit model pinning** (a specific
fast or vision model) instead of OmniRoute's auto-routing, or a model not enabled on the
NVIDIA account.

## Which backend first

1. `free` (OmniRoute) when its pool is healthy: $0, no credits burned.
2. `nvidia` when free is dry: free trial credits, strong tool-calling models.
3. `openrouter` when you want a **pinned** free/vision model, or NVIDIA is dry and
   OmniRoute's pool is exhausted: free `:free` models (rate-limited) or cheap paid ones.
4. `deepseek` for reliability-sensitive or trickier work: cheap and dependable.
5. `kimi` only when explicitly asked: premium.

## How Opus should decide

For each delegated task, Opus (cheaply, in-session) sizes it up:
- Trivial/mechanical + huge volume -> `free --model auto/cheap`, or
  `nvidia --model nvidia/nemotron-3-nano-30b-a3b` if free is dry.
- Code-shaped -> `free --model auto/coding`, or `nvidia` default
  (`nvidia/nemotron-3-super-120b-a12b`) if free is dry.
- Needs care but not paid-tier -> `nvidia --model nvidia/nemotron-3-super-120b-a12b`.
- Reliability critical -> `deepseek`.

Then it writes the tight spec, runs the worker, and reviews the diff as usual.

## Orchestration defaults (verify + commit)

Under combined orchestration (see the README's **Combined Orchestration** section), the tier
defaults are:

- **Mechanical / boilerplate** -> `free` (`auto/coding`, or `auto/cheap` for bulk).
- **Substantial but specifiable** (a whole module, a real refactor) -> `deepseek`, which is
  roughly Sonnet-class for coding.
- **Review** -> `deepseek` too. A review worker reads the diff and the brief and reports
  spec compliance and quality, for zero Claude tokens.

`--verify "<cmd>"` and `--commit "<msg>"` make a delegated task self-contained. The worker
edits, then the CLI runs the verify command; a non-zero exit prints the output and exits 2
without committing, and `--commit` only fires when verify passed (or no `--verify` was set).
So the orchestrator hands off a brief and gets back a **tested, committed** result without
spending Claude tokens on the test-and-commit cycle:

```bash
~/.claude/bin/delegate deepseek \
  --verify "npm test" \
  --commit "feat: add token refresh, per brief" \
  "<the full self-contained brief>"
```

The worker **model** still never runs shell or git. Only the caller-provided `--verify` and
`--commit` flags run commands, so the no-shell / no-git trust boundary stays intact. On
Windows, `--verify` runs through `cmd.exe`: pass one command, not a bash `&&` / `;` chain.
