#!/bin/bash
# usage-report.sh - Extract usage data from OpenClaw agent trajectory files
# Outputs JSON with per-agent, per-period token and cost summaries

AGENTS_DIR="/Users/siyang/.openclaw/agents"
OUTPUT="/Users/siyang/.openclaw/workspace-coding/usage_data.json"
TMPFILE="/tmp/usage_tmp.jsonl"

# Clear temp
> "$TMPFILE"

for agent_dir in "$AGENTS_DIR"/*/; do
  agent=$(basename "$agent_dir")
  sessions="$agent_dir/sessions"
  [ ! -d "$sessions" ] && continue

  for f in "$sessions"/*.trajectory.jsonl; do
    [ ! -f "$f" ] && continue

    # Extract model.completed events with usage data
    jq -c 'select(.type == "model.completed" and .data.usage != null) | {
      agent: "'"$agent"'",
      ts: .ts,
      runId: .runId,
      provider: .provider,
      modelId: .modelId,
      input: .data.usage.input,
      output: .data.usage.output,
      cacheRead: .data.usage.cacheRead,
      total: .data.usage.total,
      cost: (.data.usage.cost.total // 0),
      sessionId: .sessionId
    }' "$f" 2>/dev/null >> "$TMPFILE"
  done
done

# Aggregate and output clean JSON
cat "$TMPFILE" | jq -s '
  group_by(.agent) | map({
    agent: .[0].agent,
    total_runs: (map(.runId) | unique | length),
    total_calls: length,
    total_tokens: (map(.total) | add),
    total_input: (map(.input) | add),
    total_output: (map(.output) | add),
    total_cache_read: (map(.cacheRead) | add),
    total_cost: (map(.cost) | add),
    first_seen: (map(.ts) | min),
    last_seen: (map(.ts) | max),
    models: (map(.modelId) | unique),
    providers: (map(.provider) | unique),
    daily: (group_by(.ts[0:10]) | map({
      date: .[0].ts[0:10],
      calls: length,
      tokens: (map(.total) | add),
      cost: (map(.cost) | add)
    }))
  })' > "$OUTPUT"

echo "Done. Saved to $OUTPUT"
echo "Agents found: $(jq length "$OUTPUT")"
echo "Total calls: $(jq '[.[].total_calls] | add' "$OUTPUT")"
echo "Total tokens: $(jq '[.[].total_tokens] | add' "$OUTPUT")"
rm -f "$TMPFILE"
