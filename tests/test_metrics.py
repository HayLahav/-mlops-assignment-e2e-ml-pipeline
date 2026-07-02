"""Unit tests for pipeline.metrics.collect_metrics."""

import json

from pipeline.metrics import collect_metrics


def _write_summary(eval_dir, data):
    reports = eval_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "summary.json").write_text(json.dumps(data), encoding="utf-8")


def test_collect_metrics_parses_summary(tmp_path):
    _write_summary(
        tmp_path,
        {
            "total_instances": 500,
            "submitted_instances": 3,
            "completed_instances": 3,
            "resolved_instances": 1,
            "unresolved_instances": 2,
            "empty_patch_instances": 0,
            "error_instances": 0,
        },
    )
    m = collect_metrics(tmp_path)
    assert m["report_found"] is True
    assert m["submitted_instances"] == 3
    assert m["resolved_instances"] == 1
    assert m["resolved_rate"] == 0.3333
    assert m["resolved_rate_completed"] == 0.3333


def test_collect_metrics_missing_report_returns_zeros(tmp_path):
    m = collect_metrics(tmp_path)
    assert m["report_found"] is False
    assert m["resolved_instances"] == 0


def test_resolved_rate_zero_when_nothing_submitted(tmp_path):
    _write_summary(
        tmp_path,
        {"submitted_instances": 0, "completed_instances": 0, "resolved_instances": 0},
    )
    m = collect_metrics(tmp_path)
    assert m["resolved_rate"] == 0.0
    assert m["resolved_rate_completed"] == 0.0


def test_collect_metrics_finds_harness_named_report(tmp_path):
    # Fall back to a "<model>.<run_id>.json" report if summary.json is absent.
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    (reports / "model__x.run1.json").write_text(
        json.dumps({"submitted_instances": 2, "resolved_instances": 2,
                    "completed_instances": 2}),
        encoding="utf-8",
    )
    m = collect_metrics(tmp_path)
    assert m["report_found"] is True
    assert m["resolved_rate"] == 1.0
