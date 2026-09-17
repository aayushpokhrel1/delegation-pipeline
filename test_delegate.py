#!/usr/bin/env python3
"""Framework-free checks for delegate.py's pure helpers (no network). Run: python test_delegate.py"""
import base64
import os
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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all checks passed")
