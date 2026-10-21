# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-10-21)

- Head `31ec1b7` plus this sweep, pushed to `origin/master`. Working tree clean.
- 50 checks pass (`python test_delegate.py`). Plugin version `0.3.4`.
- `free` **works again** and is the default path: gateway up, `free.model` is
  `mistral/codestral-latest` in `~/.claude/delegate.config.json` (backup at
  `delegate.config.json.bak`). Verified with real delegations at $0.
- The gateway self-heals now: the Windows task runs at logon **and every 15 minutes**.
- `delegate --stats` warns above the totals when a tier's recent attempts are mostly failing.
  It will keep warning about `free` until ~20 successful free runs age out the window.

## Next: make the free tier reliable, not just working

This is the open thread, and it is the fourth time "why isn't free working?" has come up.
Today's answer is in `MODELS.md` (the phantom-capacity table and `/api/providers`); what
follows is only what has **not** been tried.

**First, read `MODELS.md` before touching anything.** Two wrong diagnoses today both came from
testing too small a sample: "the pool is empty, add keys" (wrong, the pool had 1,542 ids) and
"openrouter is dead on a 402" (wrong, that applies only to its paid ids; 17 `:free` ids work).

### The keyless pools are mostly not fixable, and that is the finding

Each failed for its own structural reason, not a missing key, so "fix the keyless pool" is
probably the wrong goal. Judge each on its merits:

- `aihorde` (164 ids) is **image generation**. Wrong model type, nothing to fix.
- `dva` (125) and `no-think` (64) bridge to a local **Devin** install you do not have.
- `aug` (28) shells out to the **Auggie CLI** (`'auggie' is not recognized`).
- `zc` (13) shells out to **zcode** (`spawn zcode ENOENT`).
- `cxa` (26) needs a **Codex app-server** transport URL configured.
- `cfp` (20) drives **Cloudflare Playground** through Playwright; plausibly the only one worth
  a try, since it may just need a browser installed. Cheap to test, unknown reliability.
- `tllm` (26) is `403 blocked by Vercel for this server egress IP`. Not yours to fix.
- `ddgw`, `felo` (11) scrape consumer chat UIs and are erroring. Fragile by nature.

Installing CLIs to chase these is a lot of surface area for tools that scrape or shell out.
The honest read is that real capacity comes from keyed providers.

### Leads worth taking instead, cheapest first

1. **Enable `cerebras`.** Already keyed, `isActive: false` in the OmniRoute dashboard. One
   toggle, and Cerebras is fast with a generous free tier. Highest value for least effort.
2. **Work out why `groq` is broken.** It is active and keyed, but ids return `not available in
   the active live catalog for provider 'groq'` and one hit a Cloudflare `403`. Looks like a
   catalog-sync problem inside OmniRoute rather than a bad key, so check whether its model
   list can be refreshed.
3. **Add another free provider key** (Gemini has a free tier; the README mentions it).
4. **Give `delegate` a model fallback list.** The real fragility is that `free` points at one
   model id, so one dead model means the whole tier is down until someone notices. A list
   tried in order would make it survive what happened today. This is a code change in
   `resolve_backend` / `agent_loop`, needs a design pass, and is the only item here that
   improves the tool rather than the environment.

### Two constraints not to rediscover

- Set the model in `delegate.config.json`, **not** with `--model`: a config default keeps the
  `free` -> `deepseek` escalation, while `--model` disables it by design.
- The escalation covers a backend being **unreachable**, not a worker being **wrong**. A failed
  `--verify` exits 2 without escalating, so a weaker free model shows up as more exit-2 runs
  to re-delegate.
