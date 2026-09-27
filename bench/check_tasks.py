#!/usr/bin/env python3
"""
check_tasks.py - prove every benchmark task is well-formed and genuinely solvable.

The benchmark only means something if each task's pytest gate fails on the pristine
fixtures and passes once the task's brief has been carried out. A test that already
passes would record a free win and silently inflate the published savings, and a test
that can never pass (or that fails for an unrelated reason such as a typo in an
import) would make the task unsolvable.

This script validates bench/tasks.json (required keys, tiers, unique ids, existing
test paths, non-trivial briefs, a reference solution directory per task) and then
runs every task's test twice against throwaway copies of bench/fixtures/:

  1. unsolved: on the pristine copy, pytest must exit NON-ZERO, which means the test
     currently fails and the task is really unsolved.
  2. solvable: with the committed reference solution from bench/solutions/<id> copied
     over a second pristine copy, pytest must exit ZERO, which means the task can be
     solved and the gate is not broken.

A task is ok only when both phases pass. The script also refuses to run when a
directory named 'solutions' exists anywhere under bench/fixtures/, because that would
hand the model under test the answers.

Usage:
    python bench/check_tasks.py

Exit code 0 when every task completed both phases, 1 otherwise. bench/fixtures/ is
never modified, only the temp copies.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SOLUTIONS = os.path.join(HERE, "solutions")
TASKS = os.path.join(HERE, "tasks.json")

REQUIRED_KEYS = ("id", "tier", "test", "brief")
VALID_TIERS = ("mechanical", "substantial")
MIN_BRIEF = 40
TAIL_LINES = 8


def load_spec(path):
    """Return (spec, error). error is a string when the file is unusable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except OSError as e:
        return None, f"cannot read {path}: {e}"
    except ValueError as e:
        return None, f"{path} is not valid JSON: {e}"
    if not isinstance(spec, dict):
        return None, f"{path} must contain a JSON object"
    if not spec.get("verify_template"):
        return None, f"{path} is missing a non-empty 'verify_template'"
    tasks = spec.get("tasks")
    if not tasks:
        return None, f"{path} has an empty 'tasks' list"
    return spec, None


def check_task(task, index, seen_ids):
    """Return an error string for one task, or None when it is well-formed."""
    if not isinstance(task, dict):
        return f"task #{index} is not a JSON object"
    for key in REQUIRED_KEYS:
        value = task.get(key)
        if not isinstance(value, str) or not value.strip():
            return f"task #{index} is missing a non-empty string '{key}'"
    if task["tier"] not in VALID_TIERS:
        return f"task '{task['id']}' has invalid tier '{task['tier']}'"
    if task["id"] in seen_ids:
        return f"duplicate task id '{task['id']}'"
    seen_ids.add(task["id"])
    test_path = os.path.join(FIXTURES, task["test"])
    if not os.path.isfile(test_path):
        return f"task '{task['id']}' test path does not exist: {task['test']}"
    if len(task["brief"]) < MIN_BRIEF:
        return (f"task '{task['id']}' brief is only {len(task['brief'])} characters, "
                f"a brief must be at least {MIN_BRIEF}")
    solution = os.path.join(SOLUTIONS, task["id"])
    if not os.path.isdir(solution) or not any(
            os.path.isfile(os.path.join(root, name))
            for root, _, names in os.walk(solution) for name in names):
        return f"no reference solution in bench/solutions/{task['id']}"
    return None


def find_leaked_solutions(root):
    """Return the first 'solutions' directory found under root, or None."""
    for dirpath, dirnames, _ in os.walk(root):
        if "solutions" in dirnames:
            return os.path.join(dirpath, "solutions")
    return None


def tail(text):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join(lines[-TAIL_LINES:])


def run_test(copy, test):
    """Run one task's test in the fixtures copy. Returns (returncode, output)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", test],
        cwd=copy, capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def fresh_copy():
    """Return a new temp copy of FIXTURES. The caller must remove it."""
    copy = tempfile.mkdtemp(prefix="check_tasks_")
    shutil.copytree(FIXTURES, copy, dirs_exist_ok=True)
    return copy


def apply_solution(copy, task_id):
    """Copy every file of SOLUTIONS/<task_id> over copy, preserving paths."""
    source = os.path.join(SOLUTIONS, task_id)
    for root, _, names in os.walk(source):
        for name in names:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, source)
            dst = os.path.join(copy, rel)
            parent = os.path.dirname(dst)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(src, dst)


def main():
    spec, error = load_spec(TASKS)
    if error:
        print(f"FAIL tasks.json: {error}")
        print("summary: 0 ok, 1 failed")
        return 1

    tasks = spec["tasks"]
    failures = 0
    seen_ids = set()
    for index, task in enumerate(tasks):
        task_id = task.get("id") if isinstance(task, dict) else None
        label = task_id if isinstance(task_id, str) and task_id else f"#{index}"
        reason = check_task(task, index, seen_ids)
        if reason:
            print(f"FAIL {label}: {reason}")
            failures += 1

    if failures:
        print(f"summary: 0 ok, {failures} failed, {len(tasks) - failures} unchecked")
        return 1

    leak = find_leaked_solutions(FIXTURES)
    if leak:
        print(f"FAIL fixtures: {leak} leaks the reference solutions into the fixtures "
              f"tree, which run_bench.py copies to the model under test")
        print(f"summary: 0 ok, 1 failed, {len(tasks)} unchecked")
        return 1

    ok = 0
    for task in tasks:
        task_id = task["id"]
        unsolved = fresh_copy()
        try:
            code, output = run_test(unsolved, task["test"])
        finally:
            shutil.rmtree(unsolved, ignore_errors=True)
        if code == 0:
            print(f"FAIL {task_id}: test already satisfied by the fixtures, "
                  f"so it would record a free win")
            print(tail(output))
            failures += 1
            continue

        solvable = fresh_copy()
        try:
            apply_solution(solvable, task_id)
            code, output = run_test(solvable, task["test"])
        finally:
            shutil.rmtree(solvable, ignore_errors=True)
        if code != 0:
            print(f"FAIL {task_id}: the reference solution in bench/solutions/{task_id} "
                  f"does not satisfy the gate, so the task is unsolvable or the gate "
                  f"is broken")
            print(tail(output))
            failures += 1
            continue

        print(f"ok {task_id}")
        ok += 1

    unchecked = len(tasks) - ok - failures
    print(f"summary: {ok} ok, {failures} failed, {unchecked} unchecked")
    return 1 if failures or unchecked else 0


if __name__ == "__main__":
    sys.exit(main())
