# Delegation benchmark results

- Baseline backend: `deepseek`  
- Worker backend: `deepseek`  
- Generated: 2026-09-17 04:54:55 UTC

Savings% = 1 - T_review / T_do, both measured on the baseline model. T_do is what the baseline spends doing the task inline; T_review is what it spends reviewing the worker's diff instead. The worker tokens (T_worker) ran on the free/cheap tier, so they cost the orchestrator nothing.

| Task | Tier | Inline ok | Worker ok | T_do (inline) | T_review (overhead) | Savings % | T_worker (offload) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| subtract | mechanical | yes | yes | 3241 | 828 | 74.5 | 3306 |
| docstrings | mechanical | yes | yes | 6349 | 861 | 86.4 | 4516 |
| money | substantial | yes | yes | 7048 | 1009 | 85.7 | 2619 |
| validate | substantial | yes | yes | 12977 | 956 | 92.6 | 9880 |

Medians: T_do=6698.5 T_review=908.5 T_worker=3911.0 savings=86.1%

Headline: median savings 86.1% with 20321 worker tokens offloaded.
