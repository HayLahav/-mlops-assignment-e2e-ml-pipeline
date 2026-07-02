"""Assemble a complete, demonstrable runs/<run-id>/ folder from sample/ data.

The Airflow agent + SWE-bench evaluation steps require Docker + Linux and run on
the VM, not on a dev laptop. This script reuses the *same* pipeline helpers
(collect_metrics, write_metrics, build_manifest) on the provided ``sample/``
outputs so the repository ships one fully-populated, reproducible run tree that
matches exactly what the DAG produces.

    python scripts/build_sample_run.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.config import build_run_config  # noqa: E402
from pipeline.manifest import build_manifest  # noqa: E402
from pipeline.metrics import collect_metrics, write_metrics  # noqa: E402
from pipeline.paths import prepare_run_dir  # noqa: E402

# Kept short so the deep SWE-bench log tree stays under the Windows MAX_PATH
# limit when this repo lives in a long OneDrive path. On the Linux VM, the DAG
# uses the full descriptive run id from build_run_config().
SAMPLE = PROJECT_ROOT / "sample"
RUN_ID = "sample"


def _copy_tree(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def main() -> None:
    run_config = build_run_config(
        {
            "run_id": RUN_ID,
            "subset": "verified",
            "split": "test",
            "workers": 5,
            "model": "nebius/moonshotai/Kimi-K2.6",
            "task_slice": "0:3",
        }
    )
    paths = prepare_run_dir(run_config)

    # 1. Agent outputs: trajectories + preds.json.
    _copy_tree(SAMPLE / "trajectories", paths.trajectories_dir)
    shutil.copyfile(SAMPLE / "trajectories" / "preds.json", paths.preds_json)

    # 2. Evaluation outputs: harness logs (renamed from the sample run_id "test"
    #    to our run_id) and the summary report.
    src_logs = SAMPLE / "logs" / "run_evaluation" / "test"
    dst_logs = paths.eval_logs_dir / "run_evaluation" / RUN_ID
    _copy_tree(src_logs, dst_logs)

    paths.eval_reports_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        SAMPLE / "nebius__moonshotai__Kimi-K2.6.test.json",
        paths.eval_reports_dir / "summary.json",
    )
    # Per-instance reports, mirroring pipeline.evaluation._collect_reports.
    for report in dst_logs.rglob("report.json"):
        shutil.copyfile(report, paths.eval_reports_dir / f"{report.parent.name}.json")

    # 3. Metrics + manifest, via the real pipeline helpers.
    metrics = collect_metrics(paths.run_eval_dir)
    write_metrics(metrics, paths)
    build_manifest(run_config, paths, metrics, artifact_uri=None, mlflow_run_id=None)

    rel = paths.root.relative_to(PROJECT_ROOT).as_posix()
    print(f"Built sample run at: {rel}")
    print(f"Metrics: {metrics}")


if __name__ == "__main__":
    main()
