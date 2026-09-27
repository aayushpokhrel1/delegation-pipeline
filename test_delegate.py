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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
