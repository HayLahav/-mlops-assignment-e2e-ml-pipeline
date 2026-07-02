"""Configurable coding-agent evaluation pipeline.

run-agent -> run-evaluation -> summarize/log, writing one reproducible
``runs/<run-id>/`` folder and logging params, metrics, and artifact references
to MLflow.

Trigger from the Airflow UI with "Trigger DAG w/ config" and override any of
the params below. Nothing about a specific experiment is hard-coded.

This is the standalone-Airflow (PythonOperator) path: it calls the helpers in
``pipeline/`` directly via subprocess. See ``evaluate_agent_docker.py`` for the
DockerOperator variant.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.models.param import Param

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Make the local ``pipeline`` package importable from the Airflow DAGs folder.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import (  # noqa: E402  (after sys.path tweak)
    build_manifest,
    build_run_config,
    collect_metrics,
    log_mlflow_run,
    prepare_run_dir,
    run_agent_batch,
    run_swebench_eval,
    upload_run_to_s3,
)
from pipeline.metrics import write_metrics  # noqa: E402
from pipeline.paths import RunPaths  # noqa: E402

# Airflow params -> the only place experiment values are configured.
PARAMS = {
    "split": Param("test", type="string", description="Dataset split, e.g. test."),
    "subset": Param(
        "verified",
        type="string",
        description="SWE-bench subset: lite, verified, full, or an org/name dataset.",
    ),
    "workers": Param(5, type="integer", minimum=1, description="Parallel workers."),
    "model": Param(
        "nebius/moonshotai/Kimi-K2.6",
        type="string",
        description="Model id passed to mini-swe-agent.",
    ),
    "task_slice": Param(
        "0:3", type=["null", "string"], description="Instance slice, e.g. '0:3'."
    ),
    "run_id": Param(
        None, type=["null", "string"], description="Explicit run id (auto if empty)."
    ),
    "cost_limit": Param(
        0, type="number", minimum=0, description="Per-run cost limit (0 = unlimited)."
    ),
    "instance_ids": Param(
        None,
        type=["null", "array"],
        description="Explicit instance ids; overrides task_slice when set.",
    ),
}

DEFAULT_ARGS = {
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="evaluate_agent",
    description="Run mini-swe-agent on SWE-bench and evaluate the patches.",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    params=PARAMS,
    default_args=DEFAULT_ARGS,
    tags=["mlops", "swe-bench", "evaluation"],
)
def evaluate_agent():
    @task
    def prepare_run(**context) -> dict:
        """Resolve params into a run config and create runs/<run-id>/config.json."""
        run_config = build_run_config(context["params"])
        prepare_run_dir(run_config)
        print(f"[prepare_run] run_id={run_config['run_id']}")
        print(f"[prepare_run] dataset={run_config['dataset_name']}")
        return run_config

    @task(execution_timeout=timedelta(hours=4))
    def run_agent(run_config: dict) -> dict:
        """Run mini-swe-agent; write trajectories + preds.json to run-agent/."""
        paths = RunPaths(run_config["run_id"], Path(run_config["runs_root"]) / run_config["run_id"])
        preds_path = run_agent_batch(run_config, paths)
        print(f"[run_agent] predictions -> {preds_path}")
        return run_config

    @task(execution_timeout=timedelta(hours=4))
    def run_eval(run_config: dict) -> dict:
        """Evaluate preds.json with SWE-bench; write logs/reports to run-eval/."""
        paths = RunPaths(run_config["run_id"], Path(run_config["runs_root"]) / run_config["run_id"])
        eval_dir = run_swebench_eval(run_config, paths.preds_json, paths)
        print(f"[run_eval] eval outputs -> {eval_dir}")
        return run_config

    @task(retries=2)
    def summarize_and_log(run_config: dict) -> dict:
        """Parse reports, write metrics.json + manifest.json, upload, log MLflow."""
        paths = RunPaths(run_config["run_id"], Path(run_config["runs_root"]) / run_config["run_id"])

        metrics = collect_metrics(paths.run_eval_dir)
        write_metrics(metrics, paths)
        print(f"[summarize] metrics={metrics}")

        # Object Storage upload is opt-in (no-op unless S3_BUCKET is set).
        artifact_uri = upload_run_to_s3(paths.root, run_config["run_id"])

        mlflow_run_id = log_mlflow_run(run_config, metrics, paths, artifact_uri)

        # Manifest is written last so it can reference the uri + mlflow run id.
        build_manifest(run_config, paths, metrics, artifact_uri, mlflow_run_id)
        return {
            "run_id": run_config["run_id"],
            "metrics": metrics,
            "artifact_uri": artifact_uri,
            "mlflow_run_id": mlflow_run_id,
        }

    config = prepare_run()
    agent_done = run_agent(config)
    eval_done = run_eval(agent_done)
    summarize_and_log(eval_done)


evaluate_agent()
