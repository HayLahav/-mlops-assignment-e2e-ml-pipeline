"""Run mini-swe-agent on a batch of SWE-bench instances.

This is the durable, parametrized replacement for ``scripts/mini-swe-bench-batch.sh``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .paths import RunPaths
from .util import run_logged


def build_agent_command(run_config: dict[str, Any], output_dir: Path) -> list[str]:
    """Construct the ``mini-extra swebench`` command from the run config."""
    cmd: list[str] = [
        "mini-extra",
        "swebench",
        "--subset",
        run_config["subset"],
        "--split",
        run_config["split"],
        "--model",
        run_config["model"],
        "--workers",
        str(run_config["workers"]),
        "-o",
        str(output_dir),
    ]

    instance_ids = run_config.get("instance_ids")
    if instance_ids:
        for iid in instance_ids:
            cmd += ["--filter", str(iid)]
    elif run_config.get("task_slice"):
        cmd += ["--slice", str(run_config["task_slice"])]

    if run_config.get("agent_config"):
        cmd += ["--config", str(run_config["agent_config"])]

    return cmd


def run_agent_batch(run_config: dict[str, Any], paths: RunPaths) -> Path:
    """Execute the agent batch and return the path to ``preds.json``.

    mini-swe-agent writes ``preds.json`` plus one directory of trajectories per
    instance into the ``-o`` folder. We point that at
    ``run-agent/trajectories/`` and copy ``preds.json`` up to
    ``run-agent/preds.json`` as the canonical prediction file for evaluation.
    """
    output_dir = paths.trajectories_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        # The starter scripts disable hard failures on cost-tracking errors.
        "MSWEA_COST_TRACKING": os.environ.get("MSWEA_COST_TRACKING", "ignore_errors"),
    }
    cost_limit = run_config.get("cost_limit")
    if cost_limit is not None:
        env["MSWEA_GLOBAL_COST_LIMIT"] = str(cost_limit)

    cmd = build_agent_command(run_config, output_dir)
    run_logged(
        cmd,
        cwd=Path(run_config["project_root"]),
        env=env,
        log_path=paths.run_agent_dir / "run-agent.log",
    )

    produced = output_dir / "preds.json"
    if not produced.exists():
        raise FileNotFoundError(
            f"mini-swe-agent did not produce preds.json at {produced}. "
            "Check run-agent.log for the agent output."
        )
    shutil.copyfile(produced, paths.preds_json)
    return paths.preds_json
