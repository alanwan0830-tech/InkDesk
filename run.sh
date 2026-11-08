#!/bin/sh
set -eu
cd "$(dirname "$0")"
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
exec /opt/homebrew/bin/uv run --python 3.12 python -m paper.server "$@"
