"""Unit tests for pipeline.config.build_run_config and helpers."""

import pytest

from pipeline.config import build_run_config, resolve_dataset_name


def test_defaults_applied_when_no_params():
    cfg = build_run_config({})
    assert cfg["split"] == "test"
    assert cfg["subset"] == "verified"
    assert cfg["workers"] == 5
    assert cfg["dataset_name"] == "princeton-nlp/SWE-bench_Verified"


def test_params_override_defaults_and_are_coerced():
    cfg = build_run_config({"workers": "8", "cost_limit": "1.5", "split": "dev"})
    assert cfg["workers"] == 8 and isinstance(cfg["workers"], int)
    assert cfg["cost_limit"] == 1.5 and isinstance(cfg["cost_limit"], float)
    assert cfg["split"] == "dev"


def test_empty_strings_are_ignored():
    # The Airflow UI sends "" for cleared optional fields -> use the default.
    cfg = build_run_config({"model": "", "run_id": "  "})
    assert cfg["model"] == "nebius/moonshotai/Kimi-K2.6"
    assert cfg["run_id"]  # auto-generated, not blank


def test_run_id_generated_when_absent_and_is_unique():
    a = build_run_config({})["run_id"]
    b = build_run_config({})["run_id"]
    assert a != b
    assert "nebius" in a  # includes the model slug


def test_explicit_run_id_is_slugified():
    cfg = build_run_config({"run_id": "my run/id:1"})
    assert cfg["run_id"] == "my_run_id_1"


def test_model_slug_uses_swebench_double_underscore():
    cfg = build_run_config({"model": "nebius/moonshotai/Kimi-K2.6"})
    assert cfg["model_slug"] == "nebius__moonshotai__Kimi-K2.6"


@pytest.mark.parametrize(
    "subset,expected",
    [
        ("verified", "princeton-nlp/SWE-bench_Verified"),
        ("lite", "princeton-nlp/SWE-bench_Lite"),
        ("VERIFIED", "princeton-nlp/SWE-bench_Verified"),
        ("my-org/custom-dataset", "my-org/custom-dataset"),
    ],
)
def test_resolve_dataset_name(subset, expected):
    assert resolve_dataset_name(subset) == expected


def test_unknown_subset_raises():
    with pytest.raises(ValueError):
        resolve_dataset_name("nonsense")
