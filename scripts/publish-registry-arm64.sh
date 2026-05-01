#!/usr/bin/env bash
set -euo pipefail

# Usage: ./publish-registry-arm64.sh [image] [user@host] [dest_path]
# Defaults: image=registry:2, user@host=admin@javitnas.ddns.net, dest_path=/mnt/md0/public/MCP-CNC

IMAGE=${1:-registry:2}
DEST=${2:-admin@javitnas.ddns.net}
DEST_PATH=${3:-/mnt/md0/public/MCP-CNC}
TMPDIR=${TMPDIR:-/tmp}

NAME=registry_arm64
TAR="$TMPDIR/${NAME}.tar"
GZ="$TAR.gz"

echo "Image: $IMAGE"
echo "Destination: $DEST:$DEST_PATH"

echo "Pulling ${IMAGE} for linux/arm64..."
docker pull --platform linux/arm64 "$IMAGE"

echo "Saving image to ${TAR}..."
docker save "$IMAGE" -o "$TAR"

echo "Compressing to ${GZ}..."
gzip -c "$TAR" > "$GZ"

echo "Copying ${GZ} to ${DEST}:${DEST_PATH}/"
scp "$GZ" "${DEST}:${DEST_PATH}/"

echo "Done. Clean up local files: removing $TAR and $GZ"
rm -f "$TAR" "$GZ"

echo "On the NAS run:
  cd ${DEST_PATH}
  gunzip ${NAME}.tar.gz
  sudo docker load -i ${NAME}.tar
  sudo docker rm -f registry || true
  sudo docker run -d --name registry --restart=unless-stopped -p 127.0.0.1:5000:5000 -v \"/mnt/md0/public/MCP-CNC/deploy/registry-caddy/data:/var/lib/registry\" registry:2
"
