#!/usr/bin/env bash
# Download offline Piper TTS voice + ensure model dirs exist
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIPER_DIR="${PIPER_DIR:-/models/piper}"
# Also place under project data for volume mounts
ALT_DIR="$ROOT/data/models/piper"

mkdir -p "$PIPER_DIR" "$ALT_DIR"

VOICE_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
FILES=(
  "en_US-lessac-medium.onnx"
  "en_US-lessac-medium.onnx.json"
)

echo "==> Downloading Piper en_US-lessac-medium"
for f in "${FILES[@]}"; do
  if [[ ! -f "$PIPER_DIR/$f" ]]; then
    curl -L --fail -o "$PIPER_DIR/$f" "$VOICE_BASE/$f?download=true" || \
      curl -L --fail -o "$PIPER_DIR/$f" "$VOICE_BASE/$f"
  else
    echo "    exists: $PIPER_DIR/$f"
  fi
  cp -f "$PIPER_DIR/$f" "$ALT_DIR/$f" 2>/dev/null || true
done

echo "==> Piper models ready in $PIPER_DIR"
ls -lh "$PIPER_DIR" || true
