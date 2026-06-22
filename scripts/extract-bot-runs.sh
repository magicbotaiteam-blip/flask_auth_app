#!/bin/bash
# extract-bot-runs.sh — Extract run events from OpenClaw agent trajectory files
# Now delegates to the Python version for speed and reliability.
# Generates /tmp/bot_runs.jsonl, uploaded to S3 by push-usage-to-s3.sh.

DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/extract-bot-runs.py" "$@"
