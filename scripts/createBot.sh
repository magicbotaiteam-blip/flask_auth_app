#!/bin/bash
# Create an agent and account to pair a telegram bot
# Usage: ./createBot.sh <bot_name> <telegram_token> <emails_file>
# Example: ./createBot.sh my_bot 123456:ABCdef emails.txt
# The emails file should contain one email per line (blank lines and lines starting with # are ignored)

set -euo pipefail

NAME=$1
TOKEN=$2
EMAILS_FILE=$3

if [ ! -f "$EMAILS_FILE" ]; then
  echo "ERROR: File '$EMAILS_FILE' not found."
  exit 1
fi

# Read all non-empty, non-comment lines from the file
ALLOW_FROM=""
while IFS= read -r line; do
  # Trim whitespace
  line="$(echo "$line" | xargs)"
  # Skip empty lines and comments
  [ -z "$line" ] && continue
  [[ "$line" == \#* ]] && continue

  PLATFORM_USER_ID=$(sqlite3 /Users/siyang/flask_auth_app/users.db \
    "SELECT platform_user_id FROM users WHERE email = '$line' LIMIT 1;" 2>/dev/null || true)

  if [ -z "$PLATFORM_USER_ID" ]; then
    echo "WARNING: No platform_user_id found for email '$line'"
  else
    if [ -z "$ALLOW_FROM" ]; then
      ALLOW_FROM="[\"$PLATFORM_USER_ID\""
    else
      ALLOW_FROM="$ALLOW_FROM, \"$PLATFORM_USER_ID\""
    fi
    echo "  Found platform_user_id '$PLATFORM_USER_ID' for $line"
  fi
done < "$EMAILS_FILE"

# Close the JSON array
if [ -n "$ALLOW_FROM" ]; then
  ALLOW_FROM="$ALLOW_FROM]"
fi

if [ -z "$ALLOW_FROM" ]; then
  echo "WARNING: No platform_user_ids found for any email in '$EMAILS_FILE'"
  echo "Creating bot without allowFrom restriction."
fi

# Add the Telegram channel account
echo ""
echo "Adding Telegram channel account '$NAME'..."
openclaw channels add --channel telegram --token "$TOKEN" --name "$NAME" --account "$NAME"

# Set allowFrom on the account via gateway config patch
if [ -n "$ALLOW_FROM" ]; then
  echo "Setting allowFrom to $ALLOW_FROM..."
  gateway config patch -p "channels.telegram.accounts.$NAME.allowFrom" -v "$ALLOW_FROM" 2>/dev/null || \
  openclaw gateway config patch -p "channels.telegram.accounts.$NAME.allowFrom" -v "$ALLOW_FROM" 2>/dev/null || \
  echo "WARNING: Could not set allowFrom via CLI. You may need to restart the gateway."
fi

# Add the agent
echo "Adding agent '${NAME}_agent'..."
openclaw agents add "${NAME}_agent" \
  --workspace "/Users/siyang/.openclaw/workspace-${NAME}" \
  --agent-dir "/Users/siyang/.openclaw/agents/${NAME}/agent" \
  --bind "telegram:${NAME}" \
  --model deepseek/deepseek-chat \
  --non-interactive

echo ""
# Save a copy of the emails file to the workspace directory
WORKSPACE_DIR="/Users/siyang/.openclaw/workspace-${NAME}"
mkdir -p "$WORKSPACE_DIR"
cp "$EMAILS_FILE" "$WORKSPACE_DIR/${NAME}_emails.txt"
echo "  Emails file saved to: $WORKSPACE_DIR/${NAME}_emails.txt"

echo ""
echo "Done! Bot '$NAME' created successfully."
echo "  Channel account: $NAME"
echo "  Agent: ${NAME}_agent"
echo "  Allowed from: ${ALLOW_FROM:-<not set (open to all)>}"
