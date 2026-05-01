#!/usr/bin/env bash
set -euo pipefail

REPO=${1:-mcp-cnc}
MODE=${2:-push} # push | load

if [ "$MODE" = "push" ]; then
  PUSH_OP="--push"
elif [ "$MODE" = "load" ]; then
  PUSH_OP="--load"
else
  echo "Unknown mode: $MODE (use 'push' or 'load')"
  exit 1
fi

if ! docker buildx inspect multiarch-builder >/dev/null 2>&1; then
  echo "Creating buildx builder 'multiarch-builder'..."
  docker buildx create --name multiarch-builder --use
fi

services=(mcp dxf-engine cam-engine catalogue linuxcnc-bridge)
for svc in "${services[@]}"; do
  echo "Building ${svc} for linux/arm64 -> ${REPO}/${svc}:latest"
  docker buildx build --platform linux/arm64 -t "${REPO}/${svc}:latest" -f "${svc}/Dockerfile" "${svc}" ${PUSH_OP}
done

echo "All done."
