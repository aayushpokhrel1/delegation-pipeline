# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-11-04)

- Plugin version `0.3.8`, which ships the onboarding work below; `0.3.6` was the last build
  the plugin directory scanner accepted.
- `GETTING-STARTED.md` is new: the from-nothing path for a newcomer on Windows. Written for
  a first external user, and dry-run end to end (unconfigured, minimal config, bad
  `default_backend`) rather than written from memory. It recommends `deepseek` first and
  `free` + `deepseek` as the destination, which is what the escalation chain was built for;
  an earlier draft led with `openrouter` and quietly undercut that design.
- `default_backend` in `~/.claude/delegate.config.json` now chooses the no-backend tier.
  It exists because the skills say to name no backend, so on a machine with no local gateway
  every delegation died after three connection failures.
- 53 checks pass (`python test_delegate.py`). The suite stopped reporting on Python 3.14
  until 2026-11-01: `TemporaryDirectory` cleanup raised on git's read-only files under
  Windows and killed the run at 35 checks, with nothing actually broken. Fixed at
  `_temp_repo_dir()` in `test_delegate.py`.
- `free` is the default path and works: gateway up, `free.model` is
  `mistral/codestral-latest` in `~/.claude/delegate.config.json` (backup at
  `delegate.config.json.bak`), two spares behind it.
- `delegate --stats` is no longer warning about any tier. The ledger holds 159 runs and
  its newest is 2026-10-26, so nothing has been delegated in the last week.
- OmniRoute is as last left: `cerebras` `isActive: false`, global and per-connection
  `proxyEnabled: true`.

## Next

Nothing open. The free tier's leads are closed with measured reasons in `MODELS.md`; read
that before reopening `groq` or `cerebras`, which are one Cloudflare 1010 ban, not two
problems. The one optional lead left is another free provider key (Gemini has a free tier),
and each new working id goes straight into `free.models`.
