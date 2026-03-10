#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_ID="211578345986"
REGION="us-east-1"
REPO="12-flow-api"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${REPO}:latest"

echo "==> Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

echo "==> Building image (linux/amd64)..."
docker build --platform linux/amd64 -t "$REPO" -f backend/Dockerfile backend/

echo "==> Tagging and pushing..."
docker tag "$REPO:latest" "$IMAGE"
docker push "$IMAGE"

echo "==> Done. Image pushed to $IMAGE"
