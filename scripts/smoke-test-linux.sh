#!/usr/bin/env bash
# Launches a packaged Linux build and checks that it starts cleanly.
#
#   scripts/smoke-test-linux.sh <build dir>     (e.g. build/linux)
#
# Needs a display (run it under `xvfb-run -a` on CI). Passes when, after
# START_WAIT seconds, the app has created its data folder (so the embedded
# Python imported every dependency), is still running, and its console log
# has no Python traceback. Uses throwaway XDG dirs, so a real library is
# never touched.
set -euo pipefail

BUILD_DIR=${1:?usage: smoke-test-linux.sh <build dir>}
START_WAIT=${START_WAIT:-30}

BIN=$(find "$BUILD_DIR" -maxdepth 1 -type f -executable ! -name "*.so*" | head -n1)
if [ -z "$BIN" ]; then
  echo "No executable found in $BUILD_DIR"
  exit 1
fi

SANDBOX=$(mktemp -d)
export XDG_DATA_HOME="$SANDBOX/data" XDG_CACHE_HOME="$SANDBOX/cache" XDG_CONFIG_HOME="$SANDBOX/config"
mkdir -p "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME"

echo "Starting $BIN"
"$BIN" > "$SANDBOX/stdout.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true; rm -rf "$SANDBOX"' EXIT

for _ in $(seq "$START_WAIT"); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 1
done

CONSOLE_LOG=$(find "$XDG_CACHE_HOME" -name console.log 2>/dev/null | head -n1)
show_logs() {
  echo "--- app stdout/stderr"; cat "$SANDBOX/stdout.log"
  echo "--- python console (${CONSOLE_LOG:-none})"; [ -n "$CONSOLE_LOG" ] && cat "$CONSOLE_LOG"
  echo "---"
}

FAILED=0
if ! kill -0 "$PID" 2>/dev/null; then
  wait "$PID" && code=0 || code=$?
  echo "::error::The app exited during startup (exit code $code)."
  FAILED=1
fi
if [ ! -f "$XDG_DATA_HOME/QuickeR/settings.json" ]; then
  echo "::error::The app did not create its settings, so its Python code did not start."
  FAILED=1
fi
if [ -n "$CONSOLE_LOG" ] && grep -q "Traceback" "$CONSOLE_LOG"; then
  echo "::error::The app logged a Python traceback."
  FAILED=1
fi

show_logs
if [ "$FAILED" -ne 0 ]; then
  exit 1
fi
echo "The app started and is running cleanly."
