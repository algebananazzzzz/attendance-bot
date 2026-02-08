#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/deploy-image.sh [--ecr-url URL] [--function-name NAME] [--tag TAG] [--login]

Environment variables (used if flags are omitted):
  ECR_REPOSITORY_URL  ECR repository URL (required)
  FUNCTION_NAME       Lambda function name (required)
  IMAGE_TAG or TAG    Docker image tag (required)
  AWS_REGION          AWS region (required only with --login)

Examples:
  ECR_REPOSITORY_URL=... FUNCTION_NAME=... IMAGE_TAG=prd-abc123 ./scripts/deploy-image.sh
  ./scripts/deploy-image.sh --ecr-url ... --function-name ... --tag prd-abc123 --login
USAGE
}

ecr_url="${ECR_REPOSITORY_URL:-}"
function_name="${FUNCTION_NAME:-}"
image_tag="${IMAGE_TAG:-${TAG:-}}"
aws_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"
do_login=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ecr-url)
      ecr_url="$2"
      shift 2
      ;;
    --function-name)
      function_name="$2"
      shift 2
      ;;
    --tag)
      image_tag="$2"
      shift 2
      ;;
    --login)
      do_login=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ecr_url" || -z "$function_name" ]]; then
  echo "Missing required ECR repository URL or function name."
  usage
  exit 1
fi

if [[ -z "$image_tag" ]]; then
  if [[ -n "${GITHUB_SHA:-}" ]]; then
    image_tag="prd-${GITHUB_SHA}"
  elif command -v git >/dev/null 2>&1; then
    image_tag="local-$(git rev-parse --short HEAD)"
  else
    image_tag="local-$(date +%Y%m%d%H%M%S)"
  fi
fi

if [[ "$do_login" -eq 1 ]]; then
  if [[ -z "$aws_region" ]]; then
    echo "AWS_REGION is required for --login."
    exit 1
  fi
  registry="${ecr_url%%/*}"
  aws ecr get-login-password --region "$aws_region" \
    | docker login --username AWS --password-stdin "$registry"
fi

image_uri="${ecr_url}:${image_tag}"

echo "Building image: $image_uri"
docker build --no-cache --pull -t "$image_uri" .

echo "Pushing image: $image_uri"
docker push "$image_uri"

echo "Updating Lambda: $function_name"
aws lambda update-function-code \
  --function-name "$function_name" \
  --image-uri "$image_uri"

echo "Done: $image_uri"
