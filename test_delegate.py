#!/usr/bin/env python3
"""Framework-free checks for delegate.py's pure helpers (no network). Run: python test_delegate.py"""
import base64
import json
import os
import sys
import tempfile

import delegate


def test_build_user_content_text_only():
    assert delegate.build_user_content("hi", []) == "hi"
    assert delegate.build_user_content("hi", None) == "hi"


def test_build_user_content_with_images():
    c = delegate.build_user_content("look", ["data:image/png;base64,AAA"])
    assert isinstance(c, list)
    assert c[0] == {"type": "text", "text": "look"}
    assert c[1]["type"] == "image_url"
    assert c[1]["image_url"]["url"] == "data:image/png;base64,AAA"


def test_guess_mime():
    assert delegate._guess_mime("a.png") == "image/png"
    assert delegate._guess_mime("a.JPG") == "image/jpeg"
    assert delegate._guess_mime("http://x/y.webp?q=1") == "image/webp"
    assert delegate._guess_mime("noext") == "image/png"  # default


def test_load_image_local_roundtrip():
    d = tempfile.mkdtemp()
    raw = b"\x89PNG\r\n\x1a\nfake"
    with open(os.path.join(d, "t.png"), "wb") as f:
        f.write(raw)
    delegate.ROOT = d  # load_image sandboxes relative paths to ROOT
    uri = delegate.load_image("t.png")
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == raw


def test_load_image_missing_raises():
    delegate.ROOT = tempfile.mkdtemp()
    try:
        delegate.load_image("nope.png")
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing file")


def test_run_verify_handles_non_ascii_output():
    """Verify output is UTF-8; decoding it as the locale codepage used to fail (Windows cp1252)."""
    delegate.ROOT = tempfile.mkdtemp()
    script = os.path.join(delegate.ROOT, "emit.py")
    with open(script, "w", encoding="utf-8") as f:
        # U+276F (vitest's failing-file marker) encodes as e2 9d af. 0x9d is one
        # of only five bytes cp1252 cannot decode, which is what made the original
        # traceback fire. Characters like the check mark decode to mojibake
        # instead and never raise, so they do not exercise the bug.
        f.write("import sys\n"
                "sys.stdout.reconfigure(encoding='utf-8')\n"
                "sys.stdout.write('\u276f ok\\n')\n")
    ok, out = delegate.run_verify(f'"{sys.executable}" "{script}"', 30)
    assert ok, out
    assert "❯" in out, out


def test_agent_loop_survives_empty_tool_result():
    """A tool returning "" used to crash the log line ([0] on an empty splitlines())."""
    delegate.ROOT = tempfile.mkdtemp()
    with open(os.path.join(delegate.ROOT, "empty.txt"), "w"):
        pass
    replies = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "1", "function": {"name": "read_file",
                                     "arguments": '{"path": "empty.txt"}'}}]}}]},
        {"choices": [{"message": {"content": "done"}}]},
    ]
    delegate.chat_completion = lambda *a, **k: replies.pop(0)
    summary, _ = delegate.agent_loop("free", "read it", 5, 30)
    assert summary == "done", summary


def test_summarize_ledger_totals():
    rows = [
        {"ts": "2026-09-01T10:00:00Z", "backend": "deepseek", "model": "deepseek-chat",
         "repo": "alpha", "prompt": 100, "completion": 50, "total": 150, "calls": 2,
         "verify": "failed", "commit": "abc1234"},
        {"ts": "2026-09-15T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "alpha", "prompt": 200, "completion": 100, "total": 300, "calls": 3,
         "verify": "passed", "commit": "skipped"},
        {"ts": "2026-09-27T10:00:00Z", "backend": "free", "repo": "beta",
         "prompt": 400, "completion": 200, "total": 600, "calls": 4,
         "verify": None, "commit": None},
    ]
    s = delegate.summarize_ledger(rows)
    assert s["runs"] == 3
    assert s["total"] == 1050
    assert s["prompt"] == 700
    assert s["completion"] == 350
    assert s["calls"] == 9
    assert s["first"] == "2026-09-01T10:00:00Z"
    assert s["last"] == "2026-09-27T10:00:00Z"
    assert s["verify_failed"] == 1
    assert s["commits"] == 1
    assert s["by_backend"]["deepseek"] == {"runs": 1, "total": 150}
    assert s["by_backend"]["free"] == {"runs": 2, "total": 900}
    assert s["by_repo"]["alpha"] == {"runs": 2, "total": 450}
    assert s["by_repo"]["beta"] == {"runs": 1, "total": 600}
    assert s["by_month"]["2026-09"] == {"runs": 3, "total": 1050}
    assert s["by_model"]["unknown"] == {"runs": 1, "total": 600}
    assert s["by_model"]["deepseek-chat"] == {"runs": 1, "total": 150}
    assert s["by_model"]["auto/coding"] == {"runs": 1, "total": 300}
    assert s["avoided"] == round(1050 * (1 - delegate.REVIEW_RATIO))
    assert s["worker_usd"] == 150 / 1e6 * delegate.WORKER_PRICE_PER_MTOK["deepseek"]


def test_summarize_ledger_empty():
    s = delegate.summarize_ledger([])
    assert s["runs"] == 0
    assert s["total"] == 0
    assert s["first"] is None
    assert s["last"] is None


def test_record_run_roundtrip():
    original = delegate.LEDGER_PATH
    try:
        d = tempfile.mkdtemp()
        delegate.LEDGER_PATH = os.path.join(d, "sub", "usage.jsonl")
        e1 = {"ts": "2026-09-01T10:00:00Z", "backend": "free", "total": 10}
        e2 = {"ts": "2026-09-02T10:00:00Z", "backend": "deepseek", "total": 20}
        assert delegate.record_run(e1) is True
        assert delegate.record_run(e2) is True
        with open(delegate.LEDGER_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        assert len(lines) == 2, lines
        assert json.loads(lines[0]) == e1
        assert json.loads(lines[1]) == e2
    finally:
        delegate.LEDGER_PATH = original


def test_stats_markdown_omits_repo_names():
    rows = [
        {"ts": "2026-09-01T10:00:00Z", "backend": "deepseek", "model": "deepseek-chat",
         "repo": "secret-client-repo", "prompt": 100, "completion": 50, "total": 150,
         "calls": 2},
        {"ts": "2026-09-15T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "another-private-thing", "prompt": 200, "completion": 100, "total": 300,
         "calls": 3},
        {"ts": "2026-09-27T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "another-private-thing", "prompt": 400, "completion": 200, "total": 600,
         "calls": 4},
    ]
    s = delegate.summarize_ledger(rows)
    md = delegate.stats_markdown(s)
    assert "secret-client-repo" not in md
    assert "another-private-thing" not in md
    assert "2 repos" in md, md
    assert "deepseek" in md
    assert "free" in md
    assert "### Measured impact" in md


def test_stats_markdown_handles_empty_totals():
    rows = [
        {"ts": "2026-09-01T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "alpha", "prompt": 0, "completion": 0, "total": 0, "calls": 0},
        {"ts": "2026-09-02T10:00:00Z", "backend": "deepseek", "model": "deepseek-chat",
         "repo": "beta", "prompt": 0, "completion": 0, "total": 0, "calls": 0},
    ]
    md = delegate.stats_markdown(delegate.summarize_ledger(rows))
    assert "| Metric | Value |" in md
    assert "```" not in md  # both fenced blocks are skipped when total is 0


def test_replace_stats_region_idempotent():
    text = ("# Title\n\n" + delegate.START_MARKER + "\n\nold\n\n"
            + delegate.END_MARKER + "\n\n## Next\n")
    once = delegate.replace_stats_region(text, "BLOCK")
    twice = delegate.replace_stats_region(once, "BLOCK")
    assert once == twice
    assert once.count("BLOCK") == 1
    assert "old" not in once
    assert "## Next" in once
    assert delegate.replace_stats_region("# no markers here\n", "BLOCK") is None
    reversed_text = (delegate.END_MARKER + "\n\n" + delegate.START_MARKER + "\n")
    assert delegate.replace_stats_region(reversed_text, "BLOCK") is None


def test_bar_clamps():
    bars = [delegate._bar(0), delegate._bar(1), delegate._bar(2.5), delegate._bar(-1)]
    assert len({len(b) for b in bars}) == 1
    assert delegate._bar(1) == "\u2588" * 20
    assert "\u2588" not in delegate._bar(0)
    assert delegate._bar(None) == delegate._bar(0)


def test_write_snapshot_strips_repo_names():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, "bench"))
    path = os.path.join(d, "bench", "ledger-snapshot.jsonl")
    rows = [
        {"ts": "2026-09-15T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "private-repo-two", "prompt": 200, "completion": 100, "total": 300,
         "calls": 3},
        {"ts": "2026-09-01T10:00:00Z", "backend": "deepseek", "model": "deepseek-chat",
         "repo": "private-repo-one", "prompt": 100, "completion": 50, "total": 150,
         "calls": 2},
        {"ts": "2026-09-27T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "private-repo-three", "prompt": 400, "completion": 200, "total": 600,
         "calls": 4},
    ]
    count = delegate.write_snapshot(rows, path)
    assert count == 3, count
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    assert len(lines) == 3, lines
    for name in ("private-repo-one", "private-repo-two", "private-repo-three"):
        assert name not in text, name
    parsed = [json.loads(line) for line in lines]
    for row in parsed:
        assert "repo" not in row, row
    # Every other field survives unchanged.
    by_ts = {row["ts"]: row for row in parsed}
    for original in rows:
        expected = {k: v for k, v in original.items() if k != "repo"}
        assert by_ts[original["ts"]] == expected, original
    # Oldest ts first, even though the rows were passed out of order.
    assert [row["ts"] for row in parsed] == [
        "2026-09-01T10:00:00Z", "2026-09-15T10:00:00Z", "2026-09-27T10:00:00Z"]


def test_write_snapshot_skips_missing_dir():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "no-such-dir", "ledger-snapshot.jsonl")
    rows = [{"ts": "2026-09-01T10:00:00Z", "backend": "free", "total": 10}]
    assert delegate.write_snapshot(rows, path) is None
    assert not os.path.exists(path)
    assert not os.path.exists(os.path.dirname(path))


def test_snapshot_roundtrips_through_summarize():
    d = tempfile.mkdtemp()
    os.mkdir(os.path.join(d, "bench"))
    path = os.path.join(d, "bench", "ledger-snapshot.jsonl")
    rows = [
        {"ts": "2026-09-01T10:00:00Z", "backend": "deepseek", "model": "deepseek-chat",
         "repo": "alpha", "prompt": 100, "completion": 50, "total": 150, "calls": 2},
        {"ts": "2026-09-15T10:00:00Z", "backend": "free", "model": "auto/coding",
         "repo": "beta", "prompt": 200, "completion": 100, "total": 300, "calls": 3},
    ]
    assert delegate.write_snapshot(rows, path) == 2
    with open(path, "r", encoding="utf-8") as f:
        written_rows = [json.loads(line) for line in f if line.strip()]
    assert (delegate.summarize_ledger(written_rows)["total"]
            == delegate.summarize_ledger(rows)["total"])
    assert list(delegate.summarize_ledger(written_rows)["by_repo"]) == ["unknown"]


def test_stats_markdown_publishes_range():
    rows = [
        {"ts": "2026-09-01T10:00:00Z", "backend": "deepseek", "model": "deepseek-chat",
         "repo": "alpha", "prompt": 100, "completion": 50, "total": 150, "calls": 2},
    ]
    md = delegate.stats_markdown(delegate.summarize_ledger(rows))
    assert str(delegate.BENCH_SAVINGS_MIN) in md, md
    assert str(delegate.BENCH_SAVINGS_MAX) in md, md
    assert f"median of {delegate.BENCH_TASK_COUNT} benchmark tasks" in md, md
    assert "bench/ledger-snapshot.jsonl" in md, md
    assert "python delegate.py --stats --ledger bench/ledger-snapshot.jsonl" in md, md


def test_bench_constants_match_results_file():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "bench", "RESULTS.md")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    savings = []
    medians_savings = None
    for line in lines:
        if line.startswith("Medians:"):
            for token in line.split():
                if token.startswith("savings="):
                    medians_savings = float(token.split("=", 1)[1].rstrip("%"))
        # A task row is: | id | tier | inline ok | worker ok | T_do | T_review | savings | T_worker |
        # Strip the empty edges a Markdown row leaves behind before indexing.
        fields = [f.strip() for f in line.strip().strip("|").split("|")]
        if len(fields) != 8 or not fields[4].isdigit():
            continue  # header, separator, or prose
        savings.append(float(fields[6]))

    assert len(savings) == delegate.BENCH_TASK_COUNT, (
        f"bench/RESULTS.md has {len(savings)} task rows but BENCH_TASK_COUNT is "
        f"{delegate.BENCH_TASK_COUNT}; update BENCH_TASK_COUNT in delegate.py "
        "(0 rows usually means the results table gained or lost a column, so the "
        "8-field row check above needs updating too)")
    assert min(savings) == delegate.BENCH_SAVINGS_MIN, (
        f"bench/RESULTS.md minimum savings is {min(savings)} but BENCH_SAVINGS_MIN is "
        f"{delegate.BENCH_SAVINGS_MIN}; update BENCH_SAVINGS_MIN in delegate.py")
    assert max(savings) == delegate.BENCH_SAVINGS_MAX, (
        f"bench/RESULTS.md maximum savings is {max(savings)} but BENCH_SAVINGS_MAX is "
        f"{delegate.BENCH_SAVINGS_MAX}; update BENCH_SAVINGS_MAX in delegate.py")
    expected_median = round((1 - delegate.REVIEW_RATIO) * 100, 1)
    assert medians_savings == expected_median, (
        f"bench/RESULTS.md Medians savings is {medians_savings} but REVIEW_RATIO gives "
        f"{expected_median}; update REVIEW_RATIO in delegate.py")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
