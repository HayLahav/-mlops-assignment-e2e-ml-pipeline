"""Build manifest.json -- the index that points at everything in a run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import RunPaths


def _rel(path: Path, root: Path) -> str | None:
    """Return ``path`` relative to ``root`` if it exists, else ``None``."""
    if not path.exists():
        return None
    return path.relative_to(root).as_posix()


def _list_instances(trajectories_dir: Path) -> list[str]:
    if not trajectories_dir.exists():
        return []
    return sorted(
        p.name for p in trajectories_dir.iterdir()
        if p.is_dir()
    )


def build_manifest(
    run_config: dict[str, Any],
    paths: RunPaths,
    metrics: dict[str, Any],
    artifact_uri: str | None = None,
    mlflow_run_id: str | None = None,
) -> dict[str, Any]:
    """Assemble and persist ``manifest.json``.

    The manifest is the single entry point: it records the config, the key
    file locations (relative to the run folder), the evaluated instances, the
    headline metrics, and where the full artifacts live (local + remote).
    """
    root = paths.root
    instances = _list_instances(paths.trajectories_dir)

    manifest: dict[str, Any] = {
        "run_id": run_config["run_id"],
        "created_at": run_config.get("created_at"),
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "split": run_config["split"],
            "subset": run_config["subset"],
            "dataset_name": run_config["dataset_name"],
            "model": run_config["model"],
            "workers": run_config["workers"],
            "task_slice": run_config.get("task_slice"),
            "cost_limit": run_config.get("cost_limit"),
        },
        "files": {
            "config": _rel(paths.config_json, root),
            "predictions": _rel(paths.preds_json, root),
            "trajectories": _rel(paths.trajectories_dir, root),
            "eval_logs": _rel(paths.eval_logs_dir, root),
            "eval_reports": _rel(paths.eval_reports_dir, root),
            "metrics": _rel(paths.metrics_json, root),
        },
        "instances": instances,
        "instance_count": len(instances),
        "metrics": metrics,
        "artifacts": {
            "local_path": str(root),
            "remote_uri": artifact_uri,
        },
        "mlflow_run_id": mlflow_run_id,
    }

    paths.manifest_json.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest
