"""Turn raw Airflow params into a fully-resolved, JSON-serializable run config.

Every experiment value lives here as a *default* and can be overridden from
Airflow params -- nothing about a specific experiment is hard-coded in the DAG
or in the shell scripts.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Default experiment values. Override any of these from Airflow params.
DEFAULTS: dict[str, Any] = {
    "split": "test",
    "subset": "verified",
    "workers": 5,
    "model": "nebius/moonshotai/Kimi-K2.6",
    # mini-swe-agent instance slice, e.g. "0:3" runs the first three tasks.
    "task_slice": "0:3",
    # 0 means "do not enforce a cost limit" (matches the starter scripts).
    "cost_limit": 0,
    # Optional explicit instance ids (list) -- if set, overrides task_slice.
    "instance_ids": None,
    # Path to a mini-swe-agent benchmark config. None -> use packaged default.
    "agent_config": None,
    # run_id is generated when not supplied.
    "run_id": None,
}

# mini-swe-agent --subset value  ->  SWE-bench HF dataset name used for eval.
SUBSET_TO_DATASET: dict[str, str] = {
    "lite": "princeton-nlp/SWE-bench_Lite",
    "verified": "princeton-nlp/SWE-bench_Verified",
    "full": "princeton-nlp/SWE-bench",
    "multimodal": "princeton-nlp/SWE-bench_Multimodal",
}


def resolve_dataset_name(subset: str) -> str:
    """Map a mini-swe-agent ``subset`` to the SWE-bench evaluation dataset.

    If ``subset`` already looks like an ``org/name`` dataset id, pass it
    through unchanged so custom datasets keep working.
    """
    key = subset.strip().lower()
    if key in SUBSET_TO_DATASET:
        return SUBSET_TO_DATASET[key]
    if "/" in subset:
        return subset
    raise ValueError(
        f"Unknown subset {subset!r}. Known subsets: "
        f"{sorted(SUBSET_TO_DATASET)} or an explicit 'org/name' dataset id."
    )


def slugify(value: str) -> str:
    """Filesystem- and MLflow-safe slug (the SWE-bench style: '/' -> '__')."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")


def generate_run_id(model: str, subset: str, split: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{slugify(model)}__{slugify(subset)}__{slugify(split)}__{ts}-{short}"


def build_run_config(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge Airflow params over :data:`DEFAULTS` and resolve derived fields.

    Returns a plain dict so it can be pushed through Airflow XCom and written
    verbatim to ``config.json``.
    """
    params = dict(params or {})
    cfg: dict[str, Any] = {**DEFAULTS}
    for key, value in params.items():
        # Treat empty strings from the Airflow UI as "not provided".
        if value is None or (isinstance(value, str) and value.strip() == ""):
            continue
        cfg[key] = value

    cfg["workers"] = int(cfg["workers"])
    cfg["cost_limit"] = float(cfg["cost_limit"])
    cfg["model"] = str(cfg["model"])
    cfg["split"] = str(cfg["split"])
    cfg["subset"] = str(cfg["subset"])

    if not cfg.get("run_id"):
        cfg["run_id"] = generate_run_id(cfg["model"], cfg["subset"], cfg["split"])
    else:
        cfg["run_id"] = slugify(str(cfg["run_id"]))

    cfg["dataset_name"] = resolve_dataset_name(cfg["subset"])
    # SWE-bench writes its summary report as "<model_slug>.<run_id>.json" and
    # names log dirs by the model, replacing "/" with "__" (double underscore).
    cfg["model_slug"] = cfg["model"].replace("/", "__")
    cfg["created_at"] = datetime.now(timezone.utc).isoformat()
    cfg["runs_root"] = str(Path(params.get("runs_root", PROJECT_ROOT / "runs")))
    cfg["project_root"] = str(PROJECT_ROOT)
    return cfg
