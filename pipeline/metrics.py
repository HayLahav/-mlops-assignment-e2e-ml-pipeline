"""Parse SWE-bench evaluation reports into a compact metrics dict."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import RunPaths

# Integer counters copied verbatim from the SWE-bench summary report.
_COUNT_FIELDS = [
    "total_instances",
    "submitted_instances",
    "completed_instances",
    "resolved_instances",
    "unresolved_instances",
    "empty_patch_instances",
    "error_instances",
]


def _find_summary(eval_dir: Path) -> Path | None:
    """Locate the SWE-bench summary report inside a run-eval directory."""
    reports = eval_dir / "reports"
    candidate = reports / "summary.json"
    if candidate.exists():
        return candidate
    # Fall back to any "<model>.<run_id>.json" the harness left behind.
    for pattern in ("*.json",):
        for path in list(reports.glob(pattern)) + list(eval_dir.glob(pattern)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(data, dict) and "resolved_instances" in data:
                return path
    return None


def collect_metrics(eval_dir: Path | str) -> dict[str, Any]:
    """Read the summary report and compute resolution rates.

    Returns a flat, MLflow-friendly dict. Falls back to zeros (with a
    ``report_found`` flag) when no summary report is present.
    """
    eval_dir = Path(eval_dir)
    summary = _find_summary(eval_dir)
    if summary is None:
        return {"report_found": False, **{f: 0 for f in _COUNT_FIELDS}}

    data = json.loads(summary.read_text(encoding="utf-8"))
    metrics: dict[str, Any] = {"report_found": True}
    for field in _COUNT_FIELDS:
        metrics[field] = int(data.get(field, 0) or 0)

    submitted = metrics["submitted_instances"]
    completed = metrics["completed_instances"]
    resolved = metrics["resolved_instances"]
    metrics["resolved_rate"] = round(resolved / submitted, 4) if submitted else 0.0
    metrics["resolved_rate_completed"] = (
        round(resolved / completed, 4) if completed else 0.0
    )
    return metrics


def write_metrics(metrics: dict[str, Any], paths: RunPaths) -> Path:
    paths.metrics_json.write_text(
        json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
    )
    return paths.metrics_json
