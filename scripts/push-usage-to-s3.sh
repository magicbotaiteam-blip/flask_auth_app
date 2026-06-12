#!/bin/bash
# push-usage-to-s3.sh — Push OpenClaw usage data to AWS S3
# Runs via cron every 30 minutes
#
# Usage:
#   ./push-usage-to-s3.sh  [optional: username]
#
# Depends on AWS credentials being set via environment variables or ~/.aws/credentials.

S3_BUCKET="flask-auth-app-uploads"
S3_PATH="usage/usage_data.json"
USAGE_FILE="/Users/siyang/.openclaw/workspace-coding/usage_data.json"
S3_RUNS_PATH="usage/bot_runs.json"
RUNS_FILE="/tmp/bot_runs.json"
LOG_FILE="/tmp/usage-s3-push.log"

# ─────────────────── Step 1: Refresh usage data ───────────────────
bash /Users/siyang/.openclaw/workspace-coding/usage-report.sh > /dev/null 2>&1

# ─────────────────── Step 2: Validate ───────────────────
if [ ! -f "$USAGE_FILE" ]; then
    echo "$(date): ERROR — Usage file not found at $USAGE_FILE" >> "$LOG_FILE"
    exit 1
fi

FILESIZE=$(stat -f%z "$USAGE_FILE" 2>/dev/null)
if [ "$FILESIZE" -lt 10 ]; then
    echo "$(date): WARNING — Usage file too small ($FILESIZE bytes), skipping push" >> "$LOG_FILE"
    exit 0
fi

# ─────────────────── Step 3: Upload usage data to S3 ───────────────────
aws s3 cp "$USAGE_FILE" "s3://$S3_BUCKET/$S3_PATH" \
    --content-type application/json \
    --cache-control "max-age=60" \
    2>&1 >> "$LOG_FILE"

if [ $? -eq 0 ]; then
    echo "$(date): SUCCESS — $FILESIZE bytes → s3://$S3_BUCKET/$S3_PATH" >> "$LOG_FILE"
else
    echo "$(date): FAILED — s3://$S3_BUCKET/$S3_PATH upload failed" >> "$LOG_FILE"
fi

# ─────────────────── Step 4: Upload bot runs log (if exists) ───────────────────
if [ -f "$RUNS_FILE" ] && [ $(stat -f%z "$RUNS_FILE" 2>/dev/null || echo 0) -gt 5 ]; then
    RUNS_SIZE=$(stat -f%z "$RUNS_FILE" 2>/dev/null)
    aws s3 cp "$RUNS_FILE" "s3://$S3_BUCKET/$S3_RUNS_PATH" \
        --content-type text/plain \
        --cache-control "max-age=60" \
        2>&1 >> "$LOG_FILE"

    if [ $? -eq 0 ]; then
        echo "$(date): SUCCESS — $RUNS_SIZE bytes → s3://$S3_BUCKET/$S3_RUNS_PATH" >> "$LOG_FILE"
    else
        echo "$(date): WARNING — bot_runs upload failed (non-critical)" >> "$LOG_FILE"
    fi
fi
