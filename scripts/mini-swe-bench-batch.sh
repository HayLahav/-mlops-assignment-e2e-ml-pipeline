#!/usr/bin/env bash
# Run mini-swe-agent on a batch of SWE-bench instances.
#
# Parametrized via environment variables so the same script works for manual
# runs, the Airflow PythonOperator path, and the DockerOperator path. Defaults
# reproduce the original ad-hoc command.
set -euo pipefail

SUBSET="${SUBSET:-verified}"
SPLIT="${SPLIT:-test}"
MODEL="${MODEL:-nebius/moonshotai/Kimi-K2.6}"
TASK_SLICE="${TASK_SLICE:-0:3}"
WORKERS="${WORKERS:-5}"
OUTPUT_DIR="${OUTPUT_DIR:-trajectories}"
AGENT_CONFIG="${AGENT_CONFIG:-}"
export MSWEA_COST_TRACKING="${MSWEA_COST_TRACKING:-ignore_errors}"

args=(
    --subset "$SUBSET"
    --split "$SPLIT"
    --model "$MODEL"
    --slice "$TASK_SLICE"
    --workers "$WORKERS"
    -o "$OUTPUT_DIR"
)
[ -n "$AGENT_CONFIG" ] && args+=(--config "$AGENT_CONFIG")

echo "+ mini-extra swebench ${args[*]}"
exec mini-extra swebench "${args[@]}"
