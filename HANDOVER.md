# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-11-08)

- Plugin version `0.3.9`, which ships the onboarding work and the doc sweep below; `0.3.6`
  was the last build the plugin directory scanner accepted.
- `GETTING-STARTED.md` is new: the from-nothing path for a newcomer on Windows. Written for
  a first external user, and dry-run end to end (unconfigured, minimal config, bad
  `default_backend`) rather than written from memory. It recommends `deepseek` first and
  `free` + `deepseek` as the destination, which is what the escalation chain was built for;
  an earlier draft led with `openrouter` and quietly undercut that design.
- `default_backend` in `~/.claude/delegate.config.json` now chooses the no-backend tier.
  It exists because the skills say to name no backend, so on a machine with no local gateway
  every delegation died after three connection failures.
- 54 checks pass (`python test_delegate.py`). The suite stopped reporting on Python 3.14
  until 2026-11-01: `TemporaryDirectory` cleanup raised on git's read-only files under
  Windows and killed the run at 35 checks, with nothing actually broken. Fixed at
  `_temp_repo_dir()` in `test_delegate.py`.
- `free` is the default path and works: gateway up, `free.model` is
  `mistral/codestral-latest` in `~/.claude/delegate.config.json` (backup at
  `delegate.config.json.bak`), two spares behind it.
- `delegate --stats` is not warning about any tier. The ledger holds 170 successful runs
  (203 lines, the rest failed attempts), newest 2026-11-04.
- The plugin directory listing is **in review**, with validation and policy warnings about
  reading an API key from the environment. Installing from the repo
  (`claude plugin marketplace add aayushpokhrel1/delegation-pipeline`) does not depend on
  that review and works now. The decision not to restructure the credential read is
  recorded at `resolve_backend()` in `delegate.py`, where someone would otherwise "fix" it.
- OmniRoute is as last left (not re-checked on 2026-11-08): `cerebras` `isActive: false`,
  global and per-connection `proxyEnabled: true`.
- The `OmniRoute Gateway` and `Delegate Stats Refresh` tasks were repointed through
  `scripts/run-hidden.vbs` by hand on 2026-11-08 and the installers were changed to match,
  so re-running them is a no-op. Verified: both live actions are the `wscript.exe` form and
  the 11:22 firing opened no window. 54 checks, version `0.3.9` and the 170-run ledger were
  re-measured the same day and were already correct here.

## Next

Nothing open. The free tier's leads are closed with measured reasons in `MODELS.md`; read
that before reopening `groq` or `cerebras`, which are one Cloudflare 1010 ban, not two
problems. The one optional lead left is another free provider key (Gemini has a free tier),
and each new working id goes straight into `free.models`.
