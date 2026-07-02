# Screenshots

Evidence captured on the Nebius VM after a completed run. Drop the PNGs here:

| File | What it should show |
|---|---|
| `airflow_dag.png` | The Airflow UI with `evaluate_agent` (or `evaluate_agent_docker`) — a successful run, all tasks green in the graph/grid view. |
| `mlflow_runs.png` | The MLflow UI runs table for experiment `coding-agent-eval`, showing logged params and metrics (`resolved_rate`, `resolved_instances`, …) across one or more runs. |
| `object_storage_artifacts.png` | Nebius Object Storage (UI or `aws s3 ls` output) listing the uploaded `runs/<run-id>.tar.gz` artifact. |

Reference them from `REPORT.md §4/§6`. Until captured, these are the pending
deliverables from the production-style path (see `scripts/vm-bringup.sh`).
