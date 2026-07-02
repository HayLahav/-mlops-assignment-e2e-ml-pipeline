# Report: Evaluation pipeline for coding-agent experiments

Turns the ad-hoc `scripts/` into a configurable, reproducible Airflow pipeline
that runs **mini-swe-agent** on SWE-bench tasks, evaluates the patches with the
**SWE-bench** harness, writes one self-describing `runs/<run-id>/` folder, and
logs params + metrics + artifact references to **MLflow**.

---

## 1. Architecture

```
                 Airflow params (split, subset, workers, model, task_slice,
                 run_id, cost_limit, instance_ids)
                          │
            ┌─────────────▼─────────────┐
            │  prepare_run              │  build_run_config() -> runs/<id>/config.json
            └─────────────┬─────────────┘
            ┌─────────────▼─────────────┐
            │  run_agent                │  mini-swe-agent batch
            │                           │  -> run-agent/trajectories/ + preds.json
            └─────────────┬─────────────┘
            ┌─────────────▼─────────────┐
            │  run_eval                 │  SWE-bench harness
            │                           │  -> run-eval/logs/ + reports/
            └─────────────┬─────────────┘
            ┌─────────────▼─────────────┐
            │  summarize_and_log        │  metrics.json + manifest.json
            │                           │  -> S3 upload (opt) -> MLflow
            └───────────────────────────┘
```

The DAG is a thin wrapper. All logic lives in the importable `pipeline/`
package so it is testable and reused identically by the DAG, the DockerOperator
variant, and `scripts/build_sample_run.py`.

| Module | Responsibility |
|---|---|
| `pipeline/config.py` | `build_run_config(params)` — merge params over defaults, generate `run_id`, resolve `subset` → SWE-bench dataset. **No experiment value is hard-coded.** |
| `pipeline/paths.py` | `RunPaths` + `prepare_run_dir` — the canonical `runs/<run-id>/` layout. |
| `pipeline/agent.py` | `run_agent_batch` — parametrized mini-swe-agent run. |
| `pipeline/evaluation.py` | `run_swebench_eval` — parametrized SWE-bench run + report collection. |
| `pipeline/metrics.py` | `collect_metrics` — parse the summary report into MLflow-friendly numbers. |
| `pipeline/manifest.py` | `build_manifest` — the index pointing at every artifact. |
| `pipeline/tracking.py` | `log_mlflow_run` — params, metrics, artifacts to MLflow. |
| `pipeline/storage.py` | `upload_run_to_s3` — opt-in tarball upload to S3-compatible storage. |

### DAGs

| File | Execution model | When to use |
|---|---|---|
| `dags/evaluate_agent.py` | **PythonOperator** — calls helpers via subprocess in the Airflow env | Standalone Airflow; simplest, fully reproducible |
| `dags/evaluate_agent_docker.py` | **DockerOperator** — agent + eval run in the project image; lightweight steps stay Python | Production-style isolation; swap to `KubernetesPodOperator` at scale |
| `dags/mini-swe-bench-single.py` | original starter (left untouched) | Setup smoke test |

---

## 2. How to trigger a run

### Standalone Airflow (easy mode)

```bash
cp .env.example .env          # add NEBIUS_API_KEY
uv sync
source .venv/bin/activate
bash run-airflow-standalone.sh # Airflow on :8080 (admin / admin)
```

Open http://localhost:8080 → **`evaluate_agent`** → *Trigger DAG w/ config* → set
params, e.g.:

```json
{"split": "test", "subset": "verified", "workers": 5,
 "model": "nebius/moonshotai/Kimi-K2.6", "task_slice": "0:3", "cost_limit": 0}
```

### Docker Compose (production-style)

```bash
docker build -t mlops-assignment:latest .   # image for the DockerOperator DAG
export HOST_PROJECT_DIR=$(pwd)              # host path for bind mounts
docker compose up -d                        # Airflow :8080, MLflow :5000
docker compose logs airflow | grep -i password   # standalone admin password
```

Trigger **`evaluate_agent_docker`** with the same params. The agent and
evaluation run in isolated containers; the Docker socket is mounted so
SWE-bench can spawn its per-instance containers.

---

## 3. Artifact layout

Every run is fully described by one folder (`runs/sample/` is committed as a
worked example, assembled from `sample/` by `scripts/build_sample_run.py`):

```
runs/<run-id>/
  config.json            # exact resolved config (reproducible inputs)
  run-agent/
    preds.json           # SWE-bench predictions (eval input)
    trajectories/        # per-instance agent trajectories, exit statuses, log
  run-eval/
    logs/                # SWE-bench harness logs (per-instance)
    reports/             # summary.json + per-instance report.json
  metrics.json           # parsed headline metrics
  manifest.json          # index -> every file + local path + remote/MLflow refs
```

`manifest.json` is the single entry point: hand someone the folder (or the S3
URI in the manifest) and they can reconstruct inputs, config, trajectories,
predictions, eval logs, and metrics.

### Remote storage (S3 / Nebius Object Storage)

Set `S3_BUCKET` (+ credentials in `.env`) and `summarize_and_log` tar.gz's the
run folder, uploads it to `s3://<bucket>/<prefix>/<run-id>.tar.gz`, records the
URI in `manifest.json`, and tags the MLflow run with it. When `S3_BUCKET` is
empty the step is a documented no-op and artifacts remain local.

---

## 4. MLflow tracking

`log_mlflow_run` creates one run per pipeline run in experiment
`coding-agent-eval`:

- **Params:** `run_id, split, subset, dataset_name, model, workers, task_slice, cost_limit`
- **Metrics:** `submitted/completed/resolved/unresolved/empty_patch/error_instances`, `resolved_rate`, `resolved_rate_completed`
- **Artifacts:** `config.json`, `metrics.json`, `manifest.json`, and the `reports/` dir
- **Tags:** `artifact_uri` (S3), `local_run_path`

Tracking URI comes from `MLFLOW_TRACKING_URI` (the Compose MLflow server, or a
local `mlruns/` store when unset). Different runs are then directly comparable
in the MLflow UI.

> Screenshots (`screenshots/airflow_dag.png`, `screenshots/mlflow_runs.png`,
> `screenshots/object_storage_artifacts.png`) are captured on the Nebius VM —
> see §6.

---

## 5. One completed run (worked example)

`runs/sample/` is a real, parsed run built from the provided `sample/` outputs
using the **same** `pipeline/` helpers the DAG uses (the agent + Docker-based
eval need Linux + Docker and run on the VM, not on a dev laptop):

| Metric | Value |
|---|---|
| dataset | `princeton-nlp/SWE-bench_Verified` (`test`) |
| model | `nebius/moonshotai/Kimi-K2.6` |
| submitted / completed | 3 / 3 |
| resolved | 1 |
| **resolved_rate** | **0.333** |

Reproduce it locally:

```bash
python scripts/build_sample_run.py   # rebuilds runs/sample/ from sample/
```

---

## 6. Rerun by run-id & next steps on the VM

- **Rerun the same config:** trigger either DAG with `{"run_id": "<id>", ...}`
  matching `runs/<id>/config.json` — the folder is recreated deterministically.
- **Inspect any past run:** open `runs/<id>/manifest.json`, or pull the S3
  tarball recorded there, or open the MLflow run of the same name.

### Pending on the Nebius VM (Linux + Docker required)

1. `docker compose up -d`, build `mlops-assignment:latest`, add `NEBIUS_API_KEY`.
2. Trigger `evaluate_agent_docker` on a small slice (e.g. `task_slice="0:3"`).
3. Set `S3_BUCKET` + Nebius Object Storage creds to exercise the upload.
4. Capture `screenshots/airflow_dag.png`, `screenshots/mlflow_runs.png`,
   `screenshots/object_storage_artifacts.png`.

---

## 7. Reliability

- `prepare_run` validates/normalizes params and fails fast on an unknown subset.
- `run_agent` / `run_eval` have 4h `execution_timeout` and 1 retry; `summarize_and_log` retries twice.
- MLflow and S3 failures are non-fatal (warn + continue) so a tracking/storage
  outage never discards a completed evaluation.
