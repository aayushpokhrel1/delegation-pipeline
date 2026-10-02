# Token-savings benchmark

Concrete evidence that delegating grunt work to a cheap-model worker removes most
of the token cost from the orchestrator (your Claude subscription).

## What it measures

Two numbers, both from real OpenAI-compatible `usage` fields, so there is nothing to take on faith.

**Offload (always on).** `delegate.py` now sums the worker's token usage across every
API call and prints a trailer on every run:

```
TOKENS: prompt=4260 completion=266 total=4526 calls=4
```

That is coding work that ran on the free/cheap tier instead of your Claude subscription.

**Savings % (the A/B).** For each task the harness measures, on one consistent baseline model:

- `T_do` - tokens to do the task agentically, end to end (`delegate.py <baseline> ...`).
- `T_review` - tokens for one call that reads the brief plus the worker's diff and verdicts it.
  This is all the orchestrator actually spends when it delegates: write a brief, skim a diff.
- `T_worker` - the worker's own tokens (the offload), run on the cheap tier.

```
savings% = 1 - T_review / T_do
```

**The ratio is NOT model independent, despite what this file used to claim here.** The
argument was that delegating replaces `T_do` worth of orchestrator tokens with `T_review`
worth whatever the orchestrator charges, so a ratio measured on deepseek carries to Opus.
That holds for the *prices* and not for the *token counts*. `T_do` and `T_review` are both
properties of the model that produced them: a run measures deepseek reviewing versus
deepseek doing, and the quantity being predicted is Opus reviewing versus Opus doing.
Worse, `delegate --stats` multiplies the ratio against *worker* tokens, which additionally
assumes deepseek and Opus spend comparable tokens on the same task. Nothing here tests that.

Treat the direction as sound (reviewing a diff is much cheaper than doing the work) and the
absolute figure as indicative. To measure it properly, run `--baseline` against an
Opus-backed OpenAI-compatible endpoint; the "no Claude key needed" convenience is exactly
what costs the claim its rigour.

## How to run

```bash
python bench/run_bench.py --worker deepseek --baseline deepseek
```

`--worker` is the backend that does the real delegated work (use `free` when OmniRoute is up;
it is the true $0 tier). `--baseline` is the model the A/B is measured on. Results are written
to `bench/RESULTS.md` and printed to stdout. Each task runs in a throwaway copy of
`fixtures/`, and every arm is gated by a pytest that fails until the task is actually done, so a
row only counts if the change really worked (`inline ok` / `worker ok` = yes).

A task whose worker arm failed is **left unscored** and excluded from the medians, and the
results file says how many of the tasks the medians cover. This is load-bearing, not tidiness:
a failed worker leaves an empty diff, an empty diff is cheap to review, and a cheap review
used to score as *high* savings, so the headline rose as the worker got worse. A free-backend
run on 2026-10-01 recorded its best number, 90.4%, on a task where the worker produced
nothing at all.

Requires `pip install pytest` and a usable backend key. Numbers vary run to run (temperature
0.2). The committed `RESULTS.md` run spans 60.7-89.7% per task with a median of 85.6%; expect
a similar spread rather than a repeatable figure.

## Checking the task set

```bash
python bench/check_tasks.py
```

This validates `tasks.json` (required keys, valid tiers, unique ids, test paths that exist,
briefs that are long enough, a reference solution directory per task) and then runs every task's
test twice against throwaway copies of `fixtures/`. First it proves the gate fails on the
pristine fixtures, so no task records a free win. Then it copies the reference solution from
`bench/solutions/<id>` over a second pristine copy and proves the gate passes, so no task is
unsolvable and no gate is broken. A task is reported `ok` only when both phases pass. Run it
after adding or editing a task; it exits non-zero if any task is malformed, already satisfied by
the pristine fixtures, or not satisfied by its reference solution.

The reference solutions live outside `bench/fixtures/` on purpose, because `run_bench.py` copies
the whole fixtures tree into the directory the model under test works in, so a solution placed
inside it would leak the answer.

## Latest result

See [RESULTS.md](RESULTS.md), which is generated, so it is the only figure worth quoting.
The committed run: median **85.6% fewer orchestrator tokens** per task over 9 tasks, with
71,116 tokens of actual coding work pushed onto the cheap tier.

Do not restate those numbers anywhere else. A hand-copied table in the top-level README kept
claiming a 4-task run and a "74-93% band" for weeks after this became a 9-task run spanning
60.7-89.7%, which is why that copy was deleted rather than corrected.

## A real orchestrator data point

`bench/run_bench.py` itself (a ~250-line, stdlib-only module) was written by a deepseek worker
under an Opus orchestrator. The worker consumed **109,058 tokens** producing it; the Opus
session spent only the brief plus a diff review. That is the same asymmetry the benchmark
measures, on the real orchestrator, on a non-toy file.

## The honest caveats

- `T_do` on the baseline model is a proxy for what the orchestrator would spend inline; the
  claim is the *ratio*, not the absolute token counts. And the ratio itself was measured with
  one model on both sides, so it is not transferable to another model without re-measuring
  (see "What it measures" above).
- The worker arm measures **reliability as well as capability**, and the two look alike in a
  single run. On 2026-10-01 the `free` backend failed 4 of 9 tasks back-to-back, yet 3 of
  those 4 passed when retried alone and the 4th never reached a model (a gateway 502). Read
  consecutive failures late in a run as a drained pool, not a weak model, and retry them
  individually before concluding anything about quality.
- `T_review` includes the full brief text, so the overhead is if anything over-counted and the
  savings reported conservatively.
- Worker/cheap-tier tokens are never counted as savings on the orchestrator side; they are
  reported separately as work moved off-subscription.
