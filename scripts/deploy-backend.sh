#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_ID="211578345986"
REGION="us-east-1"
REPO="12-flow-api"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
VERSION_FILE="backend/app/version.py"
CURRENT=$(awk -F' = ' '/^BUILD/ {print $2}' "$VERSION_FILE")
NEXT=$((CURRENT + 1))
printf 'BUILD = %d\n' "$NEXT" > "$VERSION_FILE"
echo "==> Bumped build number: ${CURRENT} → ${NEXT}"

TAG="build-${NEXT}"
IMAGE="${REGISTRY}/${REPO}:${TAG}"

echo "==> Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Building image (linux/amd64)..."
docker build --platform linux/amd64 -t "${REPO}:${TAG}" -f backend/Dockerfile backend/

echo "==> Tagging and pushing..."
docker tag "${REPO}:${TAG}" "$IMAGE"
docker push "$IMAGE"

echo "==> Done. Image pushed to $IMAGE (${TAG})"
