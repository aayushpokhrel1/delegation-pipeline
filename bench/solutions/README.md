# Reference solutions

These are reference solutions used only by `check_tasks.py` to prove that each benchmark task is
solvable and that each pytest gate is correct. They are deliberately kept OUTSIDE
`bench/fixtures/` because `run_bench.py` copies that whole tree into the directory the model
under test works in, so a solution placed inside it would leak the answer and invalidate every
published savings number. Update the matching solution whenever you change a task or its gate.
