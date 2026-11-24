# Handover

**Current state only.** Before adding a line here, ask whether it will still be true in a
month. If yes it belongs in `README.md`, `MODELS.md`, `bench/README.md`, a comment at the
code, or the vault, per `CLAUDE.md`. Do not grow this into a narrative: `git log` already
holds what was done, in more detail.

## Where things stand (2026-11-24)

- `master` is level with `origin/master`, and CI (`.github/workflows/ci.yml`) is green on all
  four jobs: Linux and Windows, Python 3.8 and 3.14, 56 checks each.
- Plugin version `0.3.10`. `0.3.6` was the last build the plugin directory scanner accepted.
- The directory **refused** `0.3.9` (unverified org: no hooks, no `allowed-tools` beyond
  Read/Grep/Glob/LS, no scripts). There is no application for Verified status. The
  `directory-plugin/` subfolder (instructions only, generated) was submitted as a new
  submission at `bb2fbfa`, Claude Code only, and is **in review** as of 2026-11-24; the old
  repo-root submission was withdrawn.
  Installing from the repo (`claude plugin marketplace add aayushpokhrel1/delegation-pipeline`)
  does not depend on the directory and works now.
- `free` is the default path and works: gateway up, `free.model` is
  `mistral/codestral-latest` in `~/.claude/delegate.config.json` (backup at
  `delegate.config.json.bak`), with the two spares from `DEFAULT_CONFIG` behind it.
- `delegate --stats` is not warning about any tier. The ledger holds 187 successful runs
  (220 lines, the rest failed attempts), newest 2026-11-24. The README's generated block
  says 185 because the stats task last ran 2026-11-23; the next run catches it up.
- OmniRoute was last checked 2026-11-08: `cerebras` `isActive: false`, global and
  per-connection `proxyEnabled: true`.

## Next

Nothing open. The free tier's leads are closed with measured reasons in `MODELS.md`; read
that before reopening `groq` or `cerebras`, which are one Cloudflare 1010 ban, not two
problems. The one optional lead left is another free provider key (Gemini has a free tier),
and each new working id goes straight into `free.models`.
