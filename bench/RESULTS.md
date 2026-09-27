# Delegation benchmark results

- Baseline backend: `deepseek`  
- Worker backend: `deepseek`  
- Generated: 2026-09-27 16:53:46 UTC

Savings% = 1 - T_review / T_do, both measured on the baseline model. T_do is what the baseline spends doing the task inline; T_review is what it spends reviewing the worker's diff instead. The worker tokens (T_worker) ran on the free/cheap tier, so they cost the orchestrator nothing.

| Task | Tier | Inline ok | Worker ok | T_do (inline) | T_review (overhead) | Savings % | T_worker (offload) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| subtract | mechanical | yes | yes | 3712 | 933 | 74.9 | 5151 |
| docstrings | mechanical | yes | yes | 7078 | 966 | 86.4 | 7088 |
| money | substantial | yes | yes | 2809 | 1105 | 60.7 | 9988 |
| validate | substantial | yes | yes | 10487 | 1083 | 89.7 | 7931 |
| extract | substantial | yes | yes | 8386 | 1217 | 85.5 | 10075 |
| median | substantial | yes | yes | 9687 | 1078 | 88.9 | 9641 |
| annotate | mechanical | yes | yes | 3899 | 1032 | 73.5 | 3900 |
| rename | mechanical | yes | yes | 8574 | 1130 | 86.8 | 8557 |
| duration | substantial | yes | yes | 9631 | 1391 | 85.6 | 8785 |

Medians: T_do=8386 T_review=1083 T_worker=8557 savings=85.6%

Headline: median savings 85.6% with 71116 worker tokens offloaded.
