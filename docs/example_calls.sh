#!/usr/bin/env bash
# Example API calls for AMIE SSOW MVP
# Usage: ./example_calls.sh <API_URL> <PDF_PATH>
# Example: ./example_calls.sh https://abc.execute-api.us-east-1.amazonaws.com/prod ./paper.pdf

set -euo pipefail

API="${1:-https://your-api-url/prod}"
PDF="${2:-./test.pdf}"

echo "═══════════════════════════════════════"
echo "  AMIE SSOW API – Example Calls"
echo "═══════════════════════════════════════"

# 1. Agent card
echo ""
echo "1. GET agent card"
curl -s "$API/.well-known/agent-card.json" | python3 -m json.tool

# 2. Get upload URL
echo ""
echo "2. POST /upload-url"
UPLOAD_RESP=$(curl -s -X POST "$API/upload-url" \
  -H "Content-Type: application/json" \
  -d '{"filename":"test-manuscript.pdf"}')
echo "$UPLOAD_RESP" | python3 -m json.tool

UPLOAD_URL=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['upload_url'])")
S3_KEY=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['s3_key'])")
BUCKET=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['bucket'])")

# 3. Upload PDF
echo ""
echo "3. PUT PDF to S3 (presigned URL)"
if [ -f "$PDF" ]; then
  curl -s -X PUT "$UPLOAD_URL" \
    -H "Content-Type: application/pdf" \
    --data-binary "@$PDF"
  echo "✓ Uploaded $PDF"
else
  echo "⚠ PDF not found at $PDF – skipping upload (task will fail)"
fi

# 4. Create task
echo ""
echo "4. POST /a2a/tasks"
TASK_RESP=$(curl -s -X POST "$API/a2a/tasks" \
  -H "Content-Type: application/json" \
  -d "{\"s3_key\":\"$S3_KEY\",\"bucket\":\"$BUCKET\"}")
echo "$TASK_RESP" | python3 -m json.tool

TASK_ID=$(echo "$TASK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
echo "Task ID: $TASK_ID"

# 5. Poll until complete
echo ""
echo "5. Polling GET /a2a/tasks/$TASK_ID ..."
for i in $(seq 1 60); do
  sleep 10
  STATUS_RESP=$(curl -s "$API/a2a/tasks/$TASK_ID")
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))")
  echo "  [${i}] status = $STATUS"
  if [ "$STATUS" = "complete" ] || [ "$STATUS" = "error" ]; then
    echo ""
    echo "Final result:"
    echo "$STATUS_RESP" | python3 -m json.tool
    break
  fi
done