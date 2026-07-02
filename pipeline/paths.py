"""Canonical on-disk layout for a single run.

Every run produces the same tree so a teammate can understand the whole run
from one folder::

    runs/<run-id>/
      config.json
      run-agent/
        preds.json
        trajectories/
      run-eval/
        logs/
        reports/
      metrics.json
      manifest.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunPaths:
    """Resolved paths for one ``runs/<run-id>/`` tree."""

    run_id: str
    root: Path

    @property
    def config_json(self) -> Path:
        return self.root / "config.json"

    @property
    def run_agent_dir(self) -> Path:
        return self.root / "run-agent"

    @property
    def trajectories_dir(self) -> Path:
        return self.run_agent_dir / "trajectories"

    @property
    def preds_json(self) -> Path:
        return self.run_agent_dir / "preds.json"

    @property
    def run_eval_dir(self) -> Path:
        return self.root / "run-eval"

    @property
    def eval_logs_dir(self) -> Path:
        return self.run_eval_dir / "logs"

    @property
    def eval_reports_dir(self) -> Path:
        return self.run_eval_dir / "reports"

    @property
    def metrics_json(self) -> Path:
        return self.root / "metrics.json"

    @property
    def manifest_json(self) -> Path:
        return self.root / "manifest.json"

    def ensure_dirs(self) -> "RunPaths":
        for d in (
            self.root,
            self.run_agent_dir,
            self.trajectories_dir,
            self.run_eval_dir,
            self.eval_logs_dir,
            self.eval_reports_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        return self


def prepare_run_dir(run_config: dict[str, Any]) -> RunPaths:
    """Create ``runs/<run-id>/`` and persist ``config.json``.

    This is the body of the ``prepare_run`` Airflow task.
    """
    runs_root = Path(run_config["runs_root"])
    paths = RunPaths(run_id=run_config["run_id"], root=runs_root / run_config["run_id"])
    paths.ensure_dirs()
    paths.config_json.write_text(
        json.dumps(run_config, indent=2, sort_keys=True), encoding="utf-8"
    )
    return paths
