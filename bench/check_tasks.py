#!/usr/bin/env python3
"""
check_tasks.py - prove every benchmark task is well-formed and genuinely unsolved.

The benchmark only means something if each task's pytest gate fails on the pristine
fixtures and passes only after the task's brief has been carried out. A test that
already passes would record a free win and silently inflate the published savings.

This script validates bench/tasks.json (required keys, tiers, unique ids, existing
test paths, non-trivial briefs) and then runs every task's test against a throwaway
copy of bench/fixtures/. A task is ok only when pytest exits NON-ZERO there, which
means the test currently fails and the task is really unsolved.

Usage:
    python bench/check_tasks.py

Exit code 0 when every check passed, 1 otherwise. bench/fixtures/ is never modified,
only the temp copy.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
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
        print(f"summary: {len(tasks) - failures} ok, {failures} failed")
        return 1

    copy = tempfile.mkdtemp(prefix="check_tasks_")
    try:
        shutil.copytree(FIXTURES, copy, dirs_exist_ok=True)
        for task in tasks:
            code, output = run_test(copy, task["test"])
            if code == 0:
                print(f"FAIL {task['id']}: test already satisfied by the fixtures, "
                      f"so it would record a free win")
                print(tail(output))
                failures += 1
            else:
                print(f"ok {task['id']}")
    finally:
        shutil.rmtree(copy, ignore_errors=True)

    print(f"summary: {len(tasks) - failures} ok, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
