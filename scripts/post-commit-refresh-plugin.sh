#!/bin/sh
# Refresh the installed plugin whenever a commit changed what the plugin ships.
#
# WHY THIS EXISTS, and why it is a hook rather than a line in the README:
# the plugin's skills and commands are *instructions*, so a stale installed copy
# does not break, it quietly steers every session in every project. That is
# exactly what happened: the installed copy sat on a Sep-17 commit for two weeks
# telling sessions to hand-pick the backend, long after the repo stopped saying
# that. A written "remember to refresh" would have failed the same way.
#
# It must be uninstall+install, NOT `claude plugin update`: update compares the
# version in .claude-plugin/plugin.json against the installed version and skips
# the copy when they match (the version string is literally the cache directory
# name, plugins/cache/<marketplace>/<plugin>/<version>/). So an edit without a
# version bump reports "already at the latest version" and changes nothing.
# Uninstall+install sidesteps version bookkeeping entirely.
#
# Install it with install.sh / install.ps1, or by hand:
#   ln -sf ../../scripts/post-commit-refresh-plugin.sh .git/hooks/post-commit
# A user-global core.hooksPath does NOT shadow this: the graphify global hook
# chains to the repo-local post-commit itself. Without such a chain, a global
# core.hooksPath would make git ignore this file entirely.

[ "${DELEGATE_SKIP_PLUGIN_REFRESH:-0}" = "1" ] && exit 0
command -v claude >/dev/null 2>&1 || exit 0

# Only the paths the plugin actually ships. A delegate.py or README commit does
# not change what sessions are told, so it must not pay for a reinstall.
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only HEAD 2>/dev/null)
echo "$CHANGED" | grep -qE '^(skills/|commands/|\.claude-plugin/)' || exit 0

# Only when this repo is the marketplace source. On a machine installing from
# GitHub, a local reinstall would pull the published copy and silently undo the
# commit that just landed.
#
# Both sides are slash-normalised before comparing: on Windows `git rev-parse`
# reports C:/Users/... while `marketplace list` prints C:\Users\..., so a plain
# match never fires and the hook silently does nothing.
#
# \134 is the backslash, written octal: `tr '\\'` makes GNU tr warn "an
# unescaped backslash at end of string is not portable" on every single commit.
REPO=$(git rev-parse --show-toplevel 2>/dev/null | tr '\134' '/') || exit 0
[ -n "$REPO" ] || exit 0
claude plugin marketplace list 2>/dev/null | tr '\134' '/' | grep -qF "$REPO" || exit 0

echo "[delegate hook] plugin files changed, reinstalling from this checkout"
claude plugin uninstall delegation-pipeline >/dev/null 2>&1
if claude plugin install delegation-pipeline >/dev/null 2>&1; then
    echo "[delegate hook] plugin refreshed (restart Claude Code to apply)"
else
    echo "[delegate hook] plugin reinstall FAILED; run it by hand:" >&2
    echo "  claude plugin install delegation-pipeline" >&2
fi
exit 0
