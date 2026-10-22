# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-10-22)

- Working tree clean, pushed to `origin/master`.
- 52 checks pass (`python test_delegate.py`). Plugin version `0.3.5`.
- `free` is the default path and works: gateway up, `free.model` is
  `mistral/codestral-latest` in `~/.claude/delegate.config.json` (backup at
  `delegate.config.json.bak`).
- A tier now carries spare model ids (`models` in a backend's config, tried after
  `model`, before the backend hop). `free` ships two spares. Verified live on
  2026-10-22: a bogus id 402'd, the run finished on the spare at $0, no `deepseek`.
- The gateway self-heals: the Windows task runs at logon **and every 15 minutes**.
- `delegate --stats` warns when a tier's recent attempts are mostly failing. It will
  keep warning about `free` until ~20 successful free runs age out the window.

## Next: the free tier's remaining leads

Lead 4 from the previous handover (a model fallback list) is **done**, and it was the only
one that was a code change. What is left is all environment, i.e. clicks and keys in
OmniRoute, not edits here. `MODELS.md` holds the measurements; read it before touching
anything, since two wrong diagnoses came from testing too small a sample.

1. **Enable `cerebras`.** Already keyed, `isActive: false` in the OmniRoute dashboard. One
   toggle, and Cerebras is fast with a generous free tier. Highest value for least effort.
2. **Work out why `groq` is broken.** Active and keyed, but ids return `not available in the
   active live catalog for provider 'groq'` and one hit a Cloudflare `403`. Looks like a
   catalog-sync problem inside OmniRoute rather than a bad key, so check whether its model
   list can be refreshed.
3. **Add another free provider key** (Gemini has a free tier; the README mentions it). Each
   new working id can go straight into `free.models`.

The keyless pools in OmniRoute's 1,542-id catalog are **not** a lead: each is structurally
unusable (image models, bridges to CLIs you do not have, blocked egress, chat-UI scrapers),
and `MODELS.md` has the per-pool table. `cfp` (Cloudflare Playground, needs a Playwright
browser) is the only one that might just work; cheap to test, unknown reliability.

### Two constraints not to rediscover

- Set the model in `delegate.config.json`, **not** with `--model`: a config default keeps the
  `free` -> `deepseek` escalation and the `models` spares, while `--model` disables both by
  design.
- The escalation covers a backend being **unreachable**, not a worker being **wrong**. A failed
  `--verify` exits 2 without escalating, so a weaker free model shows up as more exit-2 runs
  to re-delegate.
