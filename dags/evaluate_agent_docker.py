"""Production-style variant of the evaluation pipeline using DockerOperator.

The lightweight steps (config, metrics, manifest, MLflow, S3) stay as Python
tasks. The heavy, dependency-rich steps (the agent batch and the SWE-bench
evaluation) run in isolated containers built from the project ``Dockerfile``.

In large-scale production, swap ``DockerOperator`` for ``KubernetesPodOperator``.

Host configuration (set in the Airflow worker environment, e.g. via Compose):
    HOST_PROJECT_DIR   absolute path of this repo *on the Docker host*
    AGENT_IMAGE        built project image tag (default: mlops-assignment:latest)
    NEBIUS_API_KEY     inference credential, forwarded into the agent container

SWE-bench launches one Docker container per instance, so the evaluation task
mounts the host Docker socket (docker-out-of-docker).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import (  # noqa: E402
    build_manifest,
    build_run_config,
    collect_metrics,
    log_mlflow_run,
    prepare_run_dir,
    upload_run_to_s3,
)
from pipeline.evaluation import _collect_reports  # noqa: E402
from pipeline.metrics import write_metrics  # noqa: E402
from pipeline.paths import RunPaths  # noqa: E402

# Host path of the repo (DockerOperator mounts must reference host paths).
HOST_PROJECT_DIR = os.environ.get("HOST_PROJECT_DIR", str(PROJECT_ROOT))
HOST_RUNS_DIR = f"{HOST_PROJECT_DIR}/runs"
AGENT_IMAGE = os.environ.get("AGENT_IMAGE", "mlops-assignment:latest")

# In-container mount points.
CTR_RUNS = "/workspace/runs"

PARAMS = {
    "split": Param("test", type="string"),
    "subset": Param("verified", type="string"),
    "workers": Param(5, type="integer", minimum=1),
    "model": Param("nebius/moonshotai/Kimi-K2.6", type="string"),
    "task_slice": Param("0:3", type=["null", "string"]),
    "run_id": Param(None, type=["null", "string"]),
    "cost_limit": Param(0, type="number", minimum=0),
}

DEFAULT_ARGS = {"retries": 1, "retry_delay": timedelta(minutes=2)}


def _paths(run_config: dict) -> RunPaths:
    return RunPaths(
        run_config["run_id"],
        Path(run_config["runs_root"]) / run_config["run_id"],
    )


@dag(
    dag_id="evaluate_agent_docker",
    description="DockerOperator variant of the SWE-bench evaluation pipeline.",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    params=PARAMS,
    default_args=DEFAULT_ARGS,
    tags=["mlops", "swe-bench", "evaluation", "docker"],
)
def evaluate_agent_docker():
    @task
    def prepare_run(**context) -> dict:
        run_config = build_run_config(context["params"])
        prepare_run_dir(run_config)
        print(f"[prepare_run] run_id={run_config['run_id']}")
        return run_config

    config = prepare_run()
    run_id = "{{ ti.xcom_pull(task_ids='prepare_run')['run_id'] }}"
    ctr_run_dir = f"{CTR_RUNS}/{run_id}"

    # Shared mounts: the runs/ tree is writable by the containers.
    runs_mount = Mount(source=HOST_RUNS_DIR, target=CTR_RUNS, type="bind")
    docker_sock = Mount(
        source="/var/run/docker.sock", target="/var/run/docker.sock", type="bind"
    )

    run_agent = DockerOperator(
        task_id="run_agent",
        image=AGENT_IMAGE,
        command='bash -c "bash scripts/mini-swe-bench-batch.sh"',
        mounts=[runs_mount, docker_sock],
        mount_tmp_dir=False,
        auto_remove="success",
        execution_timeout=timedelta(hours=4),
        environment={
            "SUBSET": "{{ ti.xcom_pull(task_ids='prepare_run')['subset'] }}",
            "SPLIT": "{{ ti.xcom_pull(task_ids='prepare_run')['split'] }}",
            "MODEL": "{{ ti.xcom_pull(task_ids='prepare_run')['model'] }}",
            "TASK_SLICE": "{{ ti.xcom_pull(task_ids='prepare_run')['task_slice'] }}",
            "WORKERS": "{{ ti.xcom_pull(task_ids='prepare_run')['workers'] }}",
            "OUTPUT_DIR": f"{ctr_run_dir}/run-agent/trajectories",
            "MSWEA_COST_TRACKING": "ignore_errors",
            "MSWEA_GLOBAL_COST_LIMIT": "{{ ti.xcom_pull(task_ids='prepare_run')['cost_limit'] }}",
            "NEBIUS_API_KEY": os.environ.get("NEBIUS_API_KEY", ""),
        },
    )

    run_eval = DockerOperator(
        task_id="run_eval",
        image=AGENT_IMAGE,
        # Copy preds up next to the trajectories, then evaluate from run-eval/.
        command=(
            "bash -c '"
            f"cp {ctr_run_dir}/run-agent/trajectories/preds.json {ctr_run_dir}/run-agent/preds.json && "
            f"mkdir -p {ctr_run_dir}/run-eval && cd {ctr_run_dir}/run-eval && "
            "bash /mlops-assignment/scripts/swe-bench-eval.sh"
            "'"
        ),
        mounts=[runs_mount, docker_sock],
        mount_tmp_dir=False,
        auto_remove="success",
        execution_timeout=timedelta(hours=4),
        environment={
            "DATASET_NAME": "{{ ti.xcom_pull(task_ids='prepare_run')['dataset_name'] }}",
            "SPLIT": "{{ ti.xcom_pull(task_ids='prepare_run')['split'] }}",
            "PREDICTIONS_PATH": f"{ctr_run_dir}/run-agent/preds.json",
            "WORKERS": "{{ ti.xcom_pull(task_ids='prepare_run')['workers'] }}",
            "RUN_ID": run_id,
        },
    )

    @task(retries=2)
    def summarize_and_log(run_config: dict) -> dict:
        paths = _paths(run_config)
        # The containers wrote raw harness output; organize reports on the host.
        _collect_reports(run_config, paths)

        metrics = collect_metrics(paths.run_eval_dir)
        write_metrics(metrics, paths)

        artifact_uri = upload_run_to_s3(paths.root, run_config["run_id"])
        mlflow_run_id = log_mlflow_run(run_config, metrics, paths, artifact_uri)
        build_manifest(run_config, paths, metrics, artifact_uri, mlflow_run_id)
        return {"run_id": run_config["run_id"], "metrics": metrics}

    summary = summarize_and_log(config)

    config >> run_agent >> run_eval >> summary


evaluate_agent_docker()
