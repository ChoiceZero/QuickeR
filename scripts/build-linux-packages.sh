#!/usr/bin/env bash
# Build QuickeR .deb and .rpm packages from an unpacked `flet build linux` output.
#
# Usage: scripts/build-linux-packages.sh <build-dir> <version> <out-dir>
#
# Needs `nfpm` on PATH. If SIGNING_KEY_FILE points at an armored PGP private key
# (passphrase in NFPM_PASSPHRASE) both packages are signed; otherwise they are
# built unsigned.
set -euo pipefail

BUILD_DIR=$(realpath "$1")
VERSION=$2
OUT_DIR=$3

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$OUT_DIR"

# The runner binary is the only executable at the top level that isn't a library.
BIN_NAME=$(find "$BUILD_DIR" -maxdepth 1 -type f -executable ! -name "*.so*" -printf '%f\n' | head -n1)
if [ -z "$BIN_NAME" ]; then
  echo "No executable found in $BUILD_DIR" >&2
  exit 1
fi
echo "Packaging $BIN_NAME $VERSION"

export VERSION BIN_NAME BUILD_DIR
export ICON_PATH="$REPO_ROOT/src/assets/icon.png"
export DESKTOP_PATH="$REPO_ROOT/packaging/quicker.desktop"

# nfpm only expands env vars in some fields, so render the template ourselves.
CONFIG=$(mktemp --suffix=.yaml)
VARS='${VERSION} ${BIN_NAME} ${BUILD_DIR} ${ICON_PATH} ${DESKTOP_PATH} ${SIGNING_KEY_FILE}'
if [ -n "${SIGNING_KEY_FILE:-}" ]; then
  export SIGNING_KEY_FILE
  envsubst "$VARS" < "$REPO_ROOT/packaging/nfpm.yaml" > "$CONFIG"
else
  echo "::warning::No signing key provided, building unsigned packages."
  # The signature blocks are the tail of the file; drop them.
  sed '/^deb:/,$d' "$REPO_ROOT/packaging/nfpm.yaml" | envsubst "$VARS" > "$CONFIG"
fi

for fmt in deb rpm; do
  nfpm package --config "$CONFIG" --packager "$fmt" --target "$OUT_DIR/"
done
ls -l "$OUT_DIR"
