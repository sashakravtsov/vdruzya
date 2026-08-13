#!/usr/bin/env bash
# Optional: install ffmpeg for video poster frames + Inbox voice waveform decode.
# Safe to re-run; skips when already present. Does not enable a video CDN.
set -euo pipefail
if command -v ffmpeg >/dev/null 2>&1; then
  echo "OK   ffmpeg already installed: $(ffmpeg -version 2>&1 | head -1)"
  exit 0
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ffmpeg
command -v ffmpeg
ffmpeg -version 2>&1 | head -1
echo "OK   ffmpeg installed"
