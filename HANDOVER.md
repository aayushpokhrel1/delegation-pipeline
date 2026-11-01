# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-11-01)

- Working tree clean, pushed to `origin/master`. Plugin version `0.3.7`; `0.3.6` was the build the plugin directory scanner
  accepted, and the skills and commands changed since, so this bump is what ships them.
- 52 checks pass (`python test_delegate.py`). The suite stopped reporting on Python 3.14
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
