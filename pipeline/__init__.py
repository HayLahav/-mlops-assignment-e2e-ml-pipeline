"""Reusable helpers that turn the ad-hoc coding-agent scripts into an
Airflow-orchestrated, reproducible evaluation pipeline.

The Airflow DAG in ``dags/evaluate_agent.py`` is a thin wrapper around these
functions, so the same logic can be unit-tested or driven from a plain script
without Airflow.
"""

from .config import DEFAULTS, build_run_config, resolve_dataset_name
from .paths import RunPaths, prepare_run_dir
from .agent import run_agent_batch
from .evaluation import run_swebench_eval
from .metrics import collect_metrics
from .manifest import build_manifest
from .tracking import log_mlflow_run
from .storage import upload_run_to_s3

__all__ = [
    "DEFAULTS",
    "build_run_config",
    "resolve_dataset_name",
    "RunPaths",
    "prepare_run_dir",
    "run_agent_batch",
    "run_swebench_eval",
    "collect_metrics",
    "build_manifest",
    "log_mlflow_run",
    "upload_run_to_s3",
]
