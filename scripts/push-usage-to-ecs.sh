#!/bin/bash
# push-usage-to-ecs.sh — Push OpenClaw usage data to the Flask app API endpoint
# Runs after the local usage-report.sh generates usage_data.json
#
# Usage:
#   ./push-usage-to-ecs.sh [ecs-url]
#
# Default URL: https://magicbotaiteam-blip.xyz  (update this!)
# To set permanent default:
#   export USAGE_ECS_URL="https://your-app.elasticbeanstalk.com"
#   export USAGE_API_KEY="your-shared-secret-key"

# Config
USAGE_FILE="/Users/siyang/.openclaw/workspace-coding/usage_data.json"
ECS_URL="${1:-${USAGE_ECS_URL:-https://magicbotaiteam-blip.xyz}}"
API_KEY="${USAGE_API_KEY:-}"
LOG_FILE="/tmp/usage-push.log"

# Check file exists
if [ ! -f "$USAGE_FILE" ]; then
    echo "$(date): ERROR: Usage file not found at $USAGE_FILE" >> "$LOG_FILE"
    echo "ERROR: Usage file not found"
    exit 1
fi

# Get file size
FILESIZE=$(stat -f%z "$USAGE_FILE" 2>/dev/null || stat -c%s "$USAGE_FILE" 2>/dev/null || echo "0")
echo "$(date): Pushing $FILESIZE bytes to $ECS_URL/api/usage/ingest" >> "$LOG_FILE"

# Build curl command
CURL_CMD="curl -s -w '\n%{http_code}' -X POST \"$ECS_URL/api/usage/ingest\" \
    -H 'Content-Type: application/json'"

if [ -n "$API_KEY" ]; then
    CURL_CMD="$CURL_CMD -H 'X-API-Key: $API_KEY'"
fi

CURL_CMD="$CURL_CMD --data-binary @'$USAGE_FILE'"

# Execute
RESPONSE=$(eval "$CURL_CMD" 2>&1)
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "$(date): SUCCESS (HTTP $HTTP_CODE): $BODY" >> "$LOG_FILE"
    echo "SUCCESS: Usage data pushed to ECS"
else
    echo "$(date): FAILED (HTTP $HTTP_CODE): $BODY" >> "$LOG_FILE"
    echo "FAILED: HTTP $HTTP_CODE — Check $LOG_FILE for details"
fi
