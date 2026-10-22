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

**Pin a concrete model id. Do not use an `auto/*` alias.** This file used to say the
opposite, on the reasonable-sounding theory that the router fails over across healthy
providers while a pinned id commits you to one. The theory is right and the premise is not:
there is almost nothing healthy for it to fail over to, so in practice an alias fails while
a pinned id works. Measured, repeatedly, on 2026-10-21.

`delegate free --list-models` shows every alias and every concrete id, and the count is
huge: 1,542 ids on 2026-10-21. **Almost all of it is phantom capacity**, which is the single
most misleading thing about this backend. Those ids are not free API providers queueing up to
serve you, they are mostly bridges to local CLI tools you have not installed and scrapers of
consumer web chat UIs. Tested one model from each keyless pool:

| Pool | ids | What it actually is |
| --- | --- | --- |
| `aihorde` | 164 | **Image-generation** models, rejected for chat |
| `dva` | 125 | Devin bridge: `DEVIN_AGENTIC_HOME must be an absolute path` |
| `no-think` | 64 | Also the Devin catalog |
| `aug` | 28 | Auggie CLI: `'auggie' is not recognized` |
| `tllm` | 26 | `403 blocked by Vercel for this server egress IP` |
| `cxa` | 26 | Codex app-server: `transport is not configured` |
| `cfp` | 20 | Cloudflare Playground: needs a Playwright browser session |
| `zc` | 13 | `spawn zcode ENOENT`, a local binary you do not have |
| `ddgw`, `felo` | 11 | Scrapers of web chat UIs, both erroring |

So **the number of models tells you nothing about capacity.** Ask
`/api/providers` instead: it lists the connections you can actually reach, and that is the
number that matters. On 2026-10-21 it was 4 connections, 3 active (`groq`, `mistral`,
`openrouter`) with `cerebras` keyed but `isActive: false`. An `auto/*` alias ranks over the
whole phantom catalog, which is exactly why every one of them fails.

### The `auto/*` aliases route into dead OpenCode models. Pin a concrete one.

Measured 2026-10-21, with the gateway up and healthy. Every coding alias failed:
`auto/coding`, `auto/coding:reliable`, `auto/coding:fast`, `auto/best-coding` and
`auto/smart` all 502'd naming `oc/*` (OpenCode) upstreams, either deprecated
(`410 Model ... has been deprecated`) or gated (`403 OpenCode's free tier can only be used
from within OpenCode`).

**This is not an empty pool, which is what it looks like and what this file said at first.**
The gateway was serving 1,542 model ids: 954 `openrouter/`, 148 `aihorde/`, 55 `mistral/`,
18 `groq/` and just 8 `oc/`. The router was preferring those 8 dead OpenCode models over
hundreds of live ones, so the fix is the model name, not the provider keys.

What each provider actually did, tested with a tool definition attached, because the worker
edits through function calls and a model that cannot tool-call is useless here:

`/api/providers` on the gateway is the authoritative list of what you can actually reach, and
it says **4 connections, 3 active**: `groq`, `mistral`, `openrouter`, plus `cerebras`
configured but `isActive: false`. Everything else in the 1,542-id catalog (`aihorde`, `dva`,
`no-think`, `oc`, ...) is a keyless community pool you hold no connection for, which is why
the router's attempts at it come back `exhausted_connection:noauth`. Check that endpoint
before concluding anything about a model id.

| Model | Result |
| --- | --- |
| `mistral/codestral-latest`, `mistral/codestral-2508` | **Work.** Tool calls fine. The current `free` default |
| `openrouter/nvidia/nemotron-3.5-lightning:free` | **Works** |
| `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` | **Works.** Much bigger model, for a task worth the wait |
| `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | **Works** |
| `mistral/devstral-latest`, `devstral-medium-latest` | `429 Rate limit exceeded`, persistently |
| `mistral/mistral-large-latest` | `403 not available in your subscription` |
| `groq/*` | `not available in the active live catalog`, and a Cloudflare `403` |
| `openrouter/*` **paid** ids | `402 Insufficient credits. This account never purchased credits` |
| some `:free` ids (`...content-safety:free`, `...super-120b-a12b:free`) | `404 No endpoints found` |
| `oc/*` | `410` deprecated, or `403` gated |

So the free tier has **redundancy, not a single point of failure**: two providers and several
working ids. Only 17 of OpenRouter's 954 ids carry the `:free` suffix, and those are the only
OpenRouter ones reachable without credits; they are also rate-limited (~50/day) and slow, so
they suit a one-off quality run rather than volume. `codestral` is the default because it is
a code model and not day-capped.

**Enabling the `cerebras` connection would add another**, and it is already keyed and merely
switched off in the dashboard.

So `free` works today with `"model": "mistral/codestral-latest"`. Verified end to end: a real
delegation annotated a module in 3 calls and passed its test, and a second one fixed a
median function and passed, both at $0.

**Set it in `~/.claude/delegate.config.json`, NOT with `--model`.** A config default keeps the
automatic `free` -> `deepseek` escalation; `--model` deliberately disables it, because a model
id belongs to one backend. Same string, opposite behaviour on failure.

**A tier no longer rests on one id.** A backend's `models` list is tried in order after its
`model` (which still leads), and `free` ships with `mistral/codestral-2508` and
`openrouter/nvidia/nemotron-3.5-lightning:free` as spares, so a dead id costs one retry
instead of taking the tier down until someone edits the config. Verified end to end on
2026-10-22: a bogus id 402'd and the run finished on the spare, at $0, without touching
`deepseek`. `--model` skips the spares, like it skips the hop.

**The `auto/*` aliases are intermittent, not uniformly dead.** `auto/coding` served a real
delegation on 2026-10-22, the day after every alias 502'd. That does not make them worth
using: a pinned id is the predictable one, and the table below is what to pin. It does mean
"the alias failed" is evidence about one moment, not a permanent fact, so do not re-derive the
pool's health from a single alias call.

One caveat worth knowing before relying on it: the escalation covers a backend being
*unreachable*, not a worker being *wrong*. A failed `--verify` exits 2 and does not escalate,
so a weaker free model shows up as more exit-2 runs for you to re-delegate, not as automatic
fallback.
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
- Huge volume, where even a free run's latency adds up -> a cheaper pinned id, NOT
  `auto/cheap`: every `auto/*` alias ranks over the phantom catalog and fails.
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
