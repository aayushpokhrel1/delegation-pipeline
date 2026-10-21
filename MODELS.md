# Choosing a model (orchestrator cheat-sheet)

**Read this only when you have a reason to pin a model.** The backend is no longer the
orchestrator's choice: `delegate "<task>"` defaults to `free` and escalates to `deepseek` on
failure, and each backend has a default model, so the normal path needs nothing from this
file. Naming `--model` also *disables* the escalation, since a model id belongs to one
backend. Pin one for a specific capability (vision, a stronger free model, forcing a no-cost
route), not as routine practice. For `free` (OmniRoute) a pin means an `auto/*` route; for
`nvidia` and the paid backends it means a concrete model id.

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

`delegate free --list-models` shows every route alias and every concrete model id. The
catalog grows fast, so do not trust a count written here: it said "~115" while the live
gateway was serving 1,560 ids (38 of them `auto/*` routes) on 2026-10-02. Run the command.

If a route keeps 403/429-ing, the keyless pool is exhausted, add provider keys in the
OmniRoute dashboard (you have Groq/Cerebras/Gemini/Mistral/OpenRouter) or switch to `nvidia`.

**A healthy gateway does not mean a healthy pool, and the two fail differently.** On
2026-10-21, with the gateway up and answering, every coding route failed: `auto/coding`,
`auto/coding:reliable`, `auto/coding:fast`, `auto/best-coding` and `auto/smart` all returned
502s naming `oc/*` (OpenCode) upstreams that were either deprecated (`410 Model ... has been
deprecated`) or gated (`403 OpenCode's free tier can only be used from within OpenCode`).
Picking a different `auto/*` alias does not help when every alias resolves into the same dead
provider: the aliases are a preference order over one pool, not separate pools. The fix is at
the pool, by adding working provider keys at
`http://localhost:20128/dashboard/api-manager`, not at the route name. Until then `free`
fails fast and the automatic escalation to `deepseek` carries the work.
A 502 naming several providers at once (`Model is unavailable`, `exhausted_connection`) means
the pool itself has run dry rather than one route: that is the failure the automatic
`free` -> `deepseek` escalation exists to absorb.

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
| **Free vision** (image input)                | `inclusionai/ling-3.0-flash-vl:free`, `google/gemma-4-31b-it:free`, `thinkingmachines/inkling:free` | usable now (see below). `ling-3.0-flash-vl:free` saw a test image and edited in ~6s; `gemma-4-31b-it:free`'s shared free pool 429s often, retry or pin another |

**Vision (image input):** the worker can see images. Attach them at launch with
`--image <path|url>` (repeatable), or the worker can call the `view_image` tool mid-task with
a repo-relative path or an http(s) URL. Either needs a **vision-capable model**:
`delegate openrouter --model inclusionai/ling-3.0-flash-vl:free --image mockup.png "<task>"`.
Non-vision models ignore the image. Free vision models share a rate-limited pool, so a `:free`
vision id may 429; retry or pin a different one.

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

**There is no per-task sizing-up to do, and this file used to describe one here.** The CLI
defaults to `free` and falls back to `deepseek` on its own, so the normal path is
`delegate "<task>"` with no backend and no `--model`. Write the tight spec, run the worker,
review the diff.

The pins below are for a specific capability you have a reason to want:
- Huge volume, where even a free run's latency adds up -> `--model auto/cheap`.
- A stronger free model than OmniRoute's pool gives -> `nvidia --model
  nvidia/nemotron-3-super-120b-a12b`.
- Vision -> `openrouter` with a `-vl:free` model and `--image`.
- The task must not be retried from scratch -> `deepseek`.

Remember that any `--model` pin **disables the automatic fallback**, because a model id
belongs to one backend. Pinning means you have taken responsibility for the tier.

## Orchestration defaults (verify + commit)

Under combined orchestration, implementation and review both go to `delegate "<task>"` with
no backend named. A review worker reads the diff and the brief and reports spec compliance
and quality for zero Claude tokens.

`--verify` and `--commit` make a delegated task self-contained:

```bash
~/.claude/bin/delegate \
  --verify "npm test" \
  --commit "feat: add token refresh, per brief" \
  "<the full self-contained brief>"
```

**The flags' full contract, including the exit codes, lives in the README's "The
verify/commit flow".** It used to be restated here in full and the copy went stale: it
still described exit 2 as the only failure after exit 3 (worker made no edits, verify not
run) existed. One home, so this file keeps the example and not the rules.
