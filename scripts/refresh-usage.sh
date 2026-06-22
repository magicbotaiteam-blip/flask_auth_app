#!/bin/bash
# refresh-usage.sh - Refresh usage data and push to ECS
# Runs via cron on the local Mac

DIR="/Users/siyang/flask_auth_app/scripts"
cd "$DIR"

# Step 1: Extract usage data from local OpenClaw agent files
bash usage-report.sh 2>&1

# Step 2: Push to ECS (if URL is configured)
if [ -n "$USAGE_ECS_URL" ]; then
    bash push-usage-to-ecs.sh "$USAGE_ECS_URL" 2>&1
fi

# Log
echo "$(date): Usage data refreshed" >> /tmp/usage-refresh.log
