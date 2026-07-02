#!/usr/bin/env bash
# Evaluate mini-swe-agent predictions with the SWE-bench harness.
#
# Parametrized via environment variables. Defaults reproduce the original
# ad-hoc command. The harness needs Docker available (it spawns one container
# per instance), so when run inside a container the Docker socket must be
# mounted.
set -euo pipefail

DATASET_NAME="${DATASET_NAME:-princeton-nlp/SWE-bench_Verified}"
SPLIT="${SPLIT:-test}"
PREDICTIONS_PATH="${PREDICTIONS_PATH:-trajectories/preds.json}"
WORKERS="${WORKERS:-5}"
RUN_ID="${RUN_ID:-test}"

echo "+ swebench.harness.run_evaluation dataset=$DATASET_NAME run_id=$RUN_ID"
exec python -m swebench.harness.run_evaluation \
    --dataset_name "$DATASET_NAME" \
    --split "$SPLIT" \
    --predictions_path "$PREDICTIONS_PATH" \
    --max_workers "$WORKERS" \
    --run_id "$RUN_ID"
