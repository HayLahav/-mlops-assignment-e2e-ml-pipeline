"""Log a run's parameters, metrics, and artifact references to MLflow.

MLflow is optional at import time so the rest of the pipeline still works when
the package (or a tracking server) is unavailable. The tracking URI comes from
the ``MLFLOW_TRACKING_URI`` env var; when unset, MLflow falls back to a local
``mlruns/`` store, which is enough for the standalone Airflow path.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .paths import RunPaths

# Only numeric metrics are sent to MLflow's metric store.
_METRIC_KEYS = [
    "total_instances",
    "submitted_instances",
    "completed_instances",
    "resolved_instances",
    "unresolved_instances",
    "empty_patch_instances",
    "error_instances",
    "resolved_rate",
    "resolved_rate_completed",
]

_PARAM_KEYS = [
    "run_id",
    "split",
    "subset",
    "dataset_name",
    "model",
    "workers",
    "task_slice",
    "cost_limit",
]


def log_mlflow_run(
    run_config: dict[str, Any],
    metrics: dict[str, Any],
    paths: RunPaths,
    artifact_uri: str | None = None,
    log_artifacts: bool = True,
) -> str | None:
    """Create one MLflow run and return its run id (or ``None`` if disabled).

    Set ``MLFLOW_TRACKING_URI`` to point at the Compose MLflow server. Logging
    failures are swallowed (with a printed warning) so a tracking outage never
    fails the whole pipeline.
    """
    try:
        import mlflow
    except ImportError:
        print("[mlflow] not installed -- skipping experiment tracking.")
        return None

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    experiment = os.environ.get("MLFLOW_EXPERIMENT_NAME", "coding-agent-eval")
    mlflow.set_experiment(experiment)

    try:
        with mlflow.start_run(run_name=run_config["run_id"]) as active:
            mlflow.log_params(
                {k: run_config.get(k) for k in _PARAM_KEYS if run_config.get(k) is not None}
            )
            mlflow.log_metrics(
                {k: float(metrics[k]) for k in _METRIC_KEYS if k in metrics}
            )
            if artifact_uri:
                mlflow.set_tag("artifact_uri", artifact_uri)
            mlflow.set_tag("local_run_path", str(paths.root))

            if log_artifacts:
                for f in (paths.config_json, paths.metrics_json, paths.manifest_json):
                    if f.exists():
                        mlflow.log_artifact(str(f))
                if paths.eval_reports_dir.exists():
                    mlflow.log_artifacts(
                        str(paths.eval_reports_dir), artifact_path="reports"
                    )
            return active.info.run_id
    except Exception as exc:  # pragma: no cover - network/tracking issues
        print(f"[mlflow] logging failed: {exc!r}")
        return None
