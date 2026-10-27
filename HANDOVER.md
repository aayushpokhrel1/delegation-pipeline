# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-10-26)

- Working tree clean, pushed to `origin/master`.
- 52 checks pass (`python test_delegate.py`). Plugin version `0.3.6`, accepted by the
  plugin directory scanner.
- `free` is the default path and works: gateway up, `free.model` is
  `mistral/codestral-latest` in `~/.claude/delegate.config.json` (backup at
  `delegate.config.json.bak`).
- A tier now carries spare model ids (`models` in a backend's config, tried after
  `model`, before the backend hop). `free` ships two spares. Verified live on
  2026-10-22: a bogus id 402'd, the run finished on the spare at $0, no `deepseek`.
- The gateway self-heals: the Windows task runs at logon **and every 15 minutes**.
- `delegate --stats` warns when a tier's recent attempts are mostly failing. It will
  keep warning about `free` until ~20 successful free runs age out the window.

## Next: nothing open on the free tier

All four leads from the 2026-10-21 handover are closed. Lead 4 (spare model ids) shipped.
Leads 1 and 2 were chased on 2026-10-22 and are **dead ends with a measured reason**, now in
`MODELS.md`: `groq` and `cerebras` both sit behind a Cloudflare rule that 1010-bans
OmniRoute's client signature, which is not reachable from config. Read that section before
reopening either, and in particular do not re-test "is it the key / the IP / the UA / the
proxy", because all four are ruled out there with the commands that ruled them out.

The free tier's real capacity is `mistral` (not day-capped, the default) plus OpenRouter's 17
`:free` ids (~50/day, slow). That is enough for the pipeline's actual load, and a dead id now
costs one retry instead of the tier.

Lead 3 is the only one left and it is optional: **another free provider key** (Gemini has a
free tier) would widen the pool. Each new working id goes straight into `free.models`. Check
first whether the provider is Cloudflare-fronted, since that is now a known blocker rather
than a surprise.

### Two constraints not to rediscover

- Set the model in `delegate.config.json`, **not** with `--model`: a config default keeps the
  `free` -> `deepseek` escalation and the `models` spares, while `--model` disables both by
  design.
- The escalation covers a backend being **unreachable**, not a worker being **wrong**. A failed
  `--verify` exits 2 without escalating, so a weaker free model shows up as more exit-2 runs
  to re-delegate.

### OmniRoute state, as left on 2026-10-22

`cerebras` back to `isActive: false`, global and per-connection `proxyEnabled` back to `true`,
gateway restarted (pid changes; the scheduled task brings it back). `free` smoke-tested end to
end after the restart: edit + verify passed at $0. Its admin API takes the gateway's own API
key as a Bearer token: `GET /api/providers`, `GET /api/settings`,
`POST /api/providers/<id>/test`, and `PATCH` on either to change one field.
