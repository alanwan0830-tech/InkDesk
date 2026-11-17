#!/bin/sh
set -eu
cd "$(dirname "$0")"
lib_dir="$(brew --prefix cairo)/lib"
export DYLD_FALLBACK_LIBRARY_PATH="$lib_dir${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
exec uv run --python 3.12 python -m paper.server "$@"
