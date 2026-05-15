#!/bin/bash
# Deploy AMIE backend to AWS SAM
# Reads secrets from ../.env so they never get committed to GitHub

set -euo pipefail

# Load .env file
ENV_FILE="../.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found at $ENV_FILE"
  exit 1
fi

PERPLEXITY_API_KEY=$(grep PERPLEXITY_API_KEY "$ENV_FILE" | cut -d '=' -f2)

if [ -z "$PERPLEXITY_API_KEY" ]; then
  echo "ERROR: PERPLEXITY_API_KEY is empty in .env"
  exit 1
fi

echo "Building..."
sam build

echo "Deploying..."
sam deploy \
  --no-confirm-changeset \
  --parameter-overrides \
    "AllowedOrigin=\"*\" PerplexityApiKey=\"$PERPLEXITY_API_KEY\""

echo "Done!"
