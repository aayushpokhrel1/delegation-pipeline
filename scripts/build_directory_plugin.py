"""Generate directory-plugin/: the instructions-only copy submitted to the Claude plugin directory.

The directory refuses, from unverified organizations, any hook, any allowed-tools entry beyond
Read/Grep/Glob/LS, and any file that is not Markdown, text, JSON, YAML or an image. So this
copy ships the skills and commands only; the worker CLI comes from a clone + install.sh.

It is GENERATED from skills/ and commands/ so the two copies cannot drift. Never edit
directory-plugin/ by hand: edit the source and run `python scripts/build_directory_plugin.py`.
test_delegate.py fails when the committed copy is stale.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = "https://github.com/aayushpokhrel1/delegation-pipeline"

# The full plugin's skill says a SessionStart hook writes the launcher. The directory copy
# has no hook, so that paragraph is swapped. If the source wording changes, this fails loudly
# instead of shipping a claim that is false for this copy.
HOOK_PARAGRAPH = (
    "Installing this plugin is enough: a `SessionStart` hook writes the `~/.claude/bin/delegate`\n"
    "launcher pointing at the plugin's own copy. It needs Python 3.8+ on PATH; without it the hook\n"
    "writes nothing and there is no `delegate` to run. `install.sh` / `install.ps1` are only for\n"
    "working on a clone, where the launcher points at your checkout instead.\n"
)
DIRECTORY_PARAGRAPH = (
    "This copy of the plugin ships instructions only: the `~/.claude/bin/delegate` worker is not\n"
    "included. If `~/.claude/bin/delegate` does not exist, tell the user to set it up themselves\n"
    "(do not run it for them): clone " + REPO_URL + " and run its\n"
    "`install.sh` (or `install.ps1` on Windows), which needs Python 3.8+ on PATH. Do not also\n"
    "install the full plugin from that repo's marketplace, or the skills load twice.\n"
)

README = """# Delegation Pipeline (directory edition)

Generated from the main repo by `scripts/build_directory_plugin.py`; do not edit by hand.

The `/delegate` and `/orchestrate` commands and skills: hand diff-verifiable work from Claude to
free or cheap OpenAI-compatible models, then review the diff.

This edition carries the instructions only. The worker CLI is installed separately:

1. Clone {url}
2. Run `install.sh` (or `install.ps1` on Windows). Needs Python 3.8+.

Setup, backends and what leaves your machine: see the [README]({url}#readme) and
[PRIVACY.md]({url}/blob/master/PRIVACY.md).
""".format(url=REPO_URL)


def transform(text):
    # Drop allowed-tools from frontmatter: the default permission prompts apply instead.
    lines = [l for l in text.splitlines(keepends=True) if not l.startswith("allowed-tools:")]
    return "".join(lines).replace(HOOK_PARAGRAPH, DIRECTORY_PARAGRAPH)


def build(out):
    if os.path.exists(out):
        shutil.rmtree(out)
    for folder in ("skills", "commands"):
        src_dir = os.path.join(ROOT, folder)
        for dirpath, _, files in os.walk(src_dir):
            for name in files:
                src = os.path.join(dirpath, name)
                dst = os.path.join(out, os.path.relpath(src, ROOT))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(src, encoding="utf-8") as f:
                    text = f.read()
                with open(dst, "w", encoding="utf-8", newline="\n") as f:
                    f.write(transform(text))
    skill = os.path.join(out, "skills", "delegate", "SKILL.md")
    with open(skill, encoding="utf-8") as f:
        if DIRECTORY_PARAGRAPH not in f.read():
            sys.exit("skills/delegate/SKILL.md hook paragraph changed; update HOOK_PARAGRAPH")

    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["description"] = (
        manifest["description"] + " Instructions only: the worker CLI installs from the repo."
    )
    os.makedirs(os.path.join(out, ".claude-plugin"))
    with open(os.path.join(out, ".claude-plugin", "plugin.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    shutil.copy(os.path.join(ROOT, ".claude-plugin", "icon.png"), os.path.join(out, ".claude-plugin", "icon.png"))
    shutil.copy(os.path.join(ROOT, "LICENSE"), os.path.join(out, "LICENSE"))
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(README)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "directory-plugin"))
