#!/bin/bash
# log-bot-run.sh -- Log a bot run to the shared activity log
# Usage:
#   ./log-bot-run.sh <agent_name> <status> <summary>
#
# Example:
#   ./log-bot-run.sh "weather_bot" "ok" "Weather briefing sent to wife"
#   ./log-bot-run.sh "stock_tracker" "ok" "VOO: $573, SPY: $589"
#   ./log-bot-run.sh "flight_monitor" "error" "API unavailable (503)"
#
# Appends to /tmp/bot_runs.jsonl, which push-usage-to-s3.sh uploads to S3

LOG_FILE="/tmp/bot_runs.json"
AGENT="${1:-unknown}"
STATUS="${2:-ok}"
SUMMARY="${3:-}"

# Truncate summary to 200 chars max
SUMMARY="${SUMMARY:0:200}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Write JSONL entry
echo "{\"agent\":\"$AGENT\",\"timestamp\":\"$TIMESTAMP\",\"status\":\"$STATUS\",\"summary\":\"$SUMMARY\"}" >> "$LOG_FILE"
