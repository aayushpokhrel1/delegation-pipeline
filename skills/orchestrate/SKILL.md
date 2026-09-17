---
name: orchestrate
description: "Use when executing a multi-task plan or a build that should be driven off the paid Claude session: one Opus orchestrator routes each task by complexity, iteration depth, and sensitivity to the delegation pipeline (Tier B, default, zero Claude tokens) or a Claude subagent (Tier A, escape hatch). Encodes the routing table and the per-task loop (brief, route + run with --verify/--commit, review with deepseek, escalate only when needed) so the orchestrator invokes one thing instead of re-deriving it. For a single self-contained task, the delegate skill is enough; use this when there is a plan to route across tiers."
---

# orchestrate

Combined orchestration: get work done while spending as little paid Claude usage as possible.
The orchestrator plans, briefs, routes, and reviews. It never writes implementation code
itself.

## The model

- **Orchestrator** = Claude Opus in this session. The only component that spends Claude
  tokens. Holds the plan, writes each brief, routes each task, adjudicates reviews.
- **Tier B** = the delegation pipeline (`~/.claude/bin/delegate`, `free` / `deepseek` /
  `nvidia`). Zero Claude tokens. **Default tier for both implementation and review.**
- **Tier A** = Claude subagents (Agent tool: `haiku` / `sonnet` / `opus`). Costs Claude
  tokens. Escape hatch only.

## Routing (per task, three axes)

Any single axis landing in the escalate column sends that task to Tier A; otherwise Tier B.

- **Complexity:** mechanical / boilerplate -> `delegate free`; substantial but specifiable
  (a whole module, a real refactor) -> `delegate deepseek`; needs broad codebase judgment ->
  Tier A `sonnet` / `opus`.
- **Iteration depth:** verifiable in ~one shot -> Tier B; long autonomous run-fail-edit loop,
  or needs a live service / Docker / the app running -> Tier A subagent.
- **Sensitivity:** ordinary code -> Tier B; security-sensitive or full-context debugging ->
  Tier A or the orchestrator itself.

Reviews default to Tier B (`deepseek`). Pick backend/model from the live catalog
(`delegate <backend> --list-models`); the delegation-pipeline repo's `MODELS.md` has the
current shortlist.

**Cost gate (your call).** Delegation spends *your* tokens on the brief, the review, and any
re-run. Before routing to Tier B, weigh that against doing the task inline; if the brief plus
review would cost as much as or more than the edit itself, do it inline. The pipeline only
saves tokens when the work is bulkier than its description, so one-liners stay in-session.

## The loop (per task)

1. **Brief.** Tight and self-contained: exact files, the change, a pattern to mirror, exact
   values. Save to `brief.md` so review can cite it. The worker has no conversation context.
2. **Route and run** with verify + commit, so you get back a tested, committed result:
   ```
   ~/.claude/bin/delegate <free|deepseek> --verify "<test/typecheck cmd>" --commit "<msg>, per brief" "<brief>"
   ```
   `--verify` runs after editing; a non-zero exit prints output and exits 2 without
   committing. `--commit` fires only on green. On Windows `--verify` runs through `cmd.exe`,
   so pass one command, not a `&&` / `;` chain.
3. **On red** (exit 2, no commit): read the printed output and either re-delegate with the
   failure folded in as a sharper spec, or escalate that task to a Tier A subagent.
4. **Review (Tier B):** `git show HEAD > review.diff`, then
   `delegate deepseek "Review the diff in review.diff against the brief in brief.md; report spec compliance and quality, most severe first. Do not edit."`
   Adjudicate yourself: accept, fix inline, or re-delegate. Clean up scratch files after.
5. **Escalate to Tier A** only when the loop cannot converge or the task hits an axis above.

## Guardrails

- Never write implementation code yourself when a tier can do it.
- The worker **model** never runs shell or git. Only the caller's `--verify` / `--commit`
  flags run commands, so the no-shell / no-git trust boundary stays intact.
- Delegating sends repo content to external providers. Keep sensitive repos, or a session the
  user told you not to delegate, in-session on Tier A or the orchestrator.

For a single self-contained task, the `delegate` skill is enough. Reach for this when there is
a plan to route across tiers.
