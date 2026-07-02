"""Evaluate generated patches with the SWE-bench harness.

Durable, parametrized replacement for ``scripts/swe-bench-eval.sh``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .paths import RunPaths
from .util import run_logged


def build_eval_command(run_config: dict[str, Any], preds_path: Path) -> list[str]:
    return [
        "python",
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        run_config["dataset_name"],
        "--split",
        run_config["split"],
        "--predictions_path",
        str(preds_path),
        "--max_workers",
        str(run_config["workers"]),
        "--run_id",
        run_config["run_id"],
    ]


def run_swebench_eval(
    run_config: dict[str, Any], preds_path: Path, paths: RunPaths
) -> Path:
    """Run SWE-bench evaluation and return the ``run-eval`` directory.

    The harness writes per-instance logs under ``logs/run_evaluation/<run_id>/``
    and a single summary report ``<model_slug>.<run_id>.json`` into its working
    directory. We run it inside ``run-eval/`` so those land in
    ``run-eval/logs/`` and then collect the reports into ``run-eval/reports/``.
    """
    paths.run_eval_dir.mkdir(parents=True, exist_ok=True)
    paths.eval_reports_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_eval_command(run_config, preds_path)
    run_logged(
        cmd,
        cwd=paths.run_eval_dir,
        env={**os.environ},
        log_path=paths.run_eval_dir / "run-eval.log",
    )

    _collect_reports(run_config, paths)
    return paths.run_eval_dir


def _collect_reports(run_config: dict[str, Any], paths: RunPaths) -> None:
    """Move the summary report and gather per-instance reports into reports/."""
    summary_name = f"{run_config['model_slug']}.{run_config['run_id']}.json"
    summary_src = paths.run_eval_dir / summary_name
    if summary_src.exists():
        shutil.move(str(summary_src), str(paths.eval_reports_dir / "summary.json"))

    # Copy each instance's report.json next to the summary for quick access.
    log_root = paths.eval_logs_dir / "run_evaluation" / run_config["run_id"]
    if log_root.exists():
        for report in log_root.rglob("report.json"):
            instance_id = report.parent.name
            shutil.copyfile(report, paths.eval_reports_dir / f"{instance_id}.json")
