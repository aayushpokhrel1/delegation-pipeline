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

The ratio is model independent: whatever your orchestrator charges per token, delegating
replaces `T_do` worth of it with `T_review` worth. So a ratio measured on deepseek transfers
to Opus without needing a Claude backend key.

## How to run

```bash
python bench/run_bench.py --worker deepseek --baseline deepseek
```

`--worker` is the backend that does the real delegated work (use `free` when OmniRoute is up;
it is the true $0 tier). `--baseline` is the model the A/B is measured on. Results are written
to `bench/RESULTS.md` and printed to stdout. Each task runs in a throwaway copy of
`fixtures/`, and every arm is gated by a pytest that fails until the task is actually done, so a
row only counts if the change really worked (`inline ok` / `worker ok` = yes).

Requires `pip install pytest` and a usable backend key. Numbers vary run to run (temperature
0.2); across runs the per-task savings land in roughly the 74-93% band, median ~75-86%.

## Latest result

See [RESULTS.md](RESULTS.md). A representative run: median **86% fewer orchestrator tokens**
per task, with ~20k tokens of actual coding work pushed onto the cheap tier across four tasks.

## A real orchestrator data point

`bench/run_bench.py` itself (a ~250-line, stdlib-only module) was written by a deepseek worker
under an Opus orchestrator. The worker consumed **109,058 tokens** producing it; the Opus
session spent only the brief plus a diff review. That is the same asymmetry the benchmark
measures, on the real orchestrator, on a non-toy file.

## The honest caveats

- `T_do` on the baseline model is a proxy for what the orchestrator would spend inline; the
  claim is the *ratio*, not the absolute token counts.
- `T_review` includes the full brief text, so the overhead is if anything over-counted and the
  savings reported conservatively.
- Worker/cheap-tier tokens are never counted as savings on the orchestrator side; they are
  reported separately as work moved off-subscription.
