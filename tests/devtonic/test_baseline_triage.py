"""Behaviour tests for the triage helpers in scripts/devtonic/baseline.py:
failure reasons in results and ``--failing-from`` reruns."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "devtonic" / "baseline.py"


@pytest.fixture(scope="module")
def baseline():
    spec = importlib.util.spec_from_file_location("devtonic_baseline_triage", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def _write(baseline, path: Path, *results) -> Path:
    path.write_text(json.dumps([dict(baseline.asdict(r), status=r.status) for r in results]))
    return path


def test_real_failure_reason_lands_in_json_and_markdown(baseline, tmp_path, monkeypatch):
    long_tail = "x" * 300
    probe = tmp_path / "test_probe.py"
    probe.write_text(
        "def test_ok():\n    pass\n"
        f"def test_boom():\n    raise RuntimeError('git no longer recognizes {long_tail}')\n"
    )
    monkeypatch.setattr(baseline, "REPO_ROOT", tmp_path)
    out = tmp_path / "out.json"
    md = tmp_path / "out.md"

    assert baseline.main([probe.name, "--json", str(out), "--markdown", str(md)]) == 1

    node = f"{probe.name}::test_boom"
    row = json.loads(out.read_text())[0]
    assert row["failures"] == [node]
    reason = row["reasons"][node]
    # Not cut at the 80-column terminal width, but capped to one readable line.
    assert reason.startswith("RuntimeError: git no longer recognizes xxxx")
    assert len(reason) == baseline.REASON_MAX and reason.endswith("...")
    assert f"`{node}` — RuntimeError: git no longer recognizes" in md.read_text()


def test_rerun_keeps_the_isolated_runs_reason(baseline, monkeypatch):
    first = baseline.TargetResult(
        "tests/x", 1, 9.0, {"failed": 2}, "", ["tests/x/test_a.py::t", "tests/x/test_b.py::t"],
        reasons={"tests/x/test_a.py::t": "Timeout under load", "tests/x/test_b.py::t": "under load"},
    )
    reruns = {
        "tests/x/test_a.py": baseline.TargetResult("tests/x/test_a.py", 0, 1.0, {"passed": 1}, "", []),
        "tests/x/test_b.py": baseline.TargetResult(
            "tests/x/test_b.py", 1, 1.0, {"failed": 1}, "", ["tests/x/test_b.py::t"],
            reasons={"tests/x/test_b.py::t": "AssertionError: alone"},
        ),
    }
    monkeypatch.setattr(baseline, "run_target", lambda f, *_a: reruns[f])
    res = baseline.rerun_failed(first, 10, [])
    assert res.flaky == ["tests/x/test_a.py"]
    assert res.reasons == {"tests/x/test_b.py::t": "AssertionError: alone"}


def test_results_without_reasons_still_load(baseline, tmp_path):
    """JSON written before reasons existed (older CI artifacts) stays mergeable."""
    old = tmp_path / "old.json"
    old.write_text(json.dumps([{
        "target": "tests/a", "returncode": 1, "seconds": 1.0, "counts": {"failed": 1},
        "summary": "1 failed", "failures": ["tests/a/test_x.py::t"], "flaky": [], "status": "fail",
    }]))
    (res,) = baseline.load_results([old])
    assert res.reasons == {} and res.status == "fail"


def test_failing_from_reruns_only_the_reported_files(baseline, tmp_path, monkeypatch):
    a = baseline.TargetResult(
        "tests/a", 1, 1.0, {}, "",
        ["tests/a/test_x.py::t1", "tests/a/test_x.py::t2", "tests/a/test_slow.py (timeout after 300s)"],
    )
    b = baseline.TargetResult("tests/b", 0, 1.0, {"passed": 4}, "", [], ["tests/b/test_flaky.py"])
    c = baseline.TargetResult("tests/c", 1, 1.0, {}, "", ["tests/a/test_x.py::t1", "tests/c/test_z.py"])
    files = [_write(baseline, tmp_path / "1.json", a, b), _write(baseline, tmp_path / "2.json", c)]
    for rel in ("tests/a/test_x.py", "tests/a/test_slow.py", "tests/c/test_z.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")
    monkeypatch.setattr(baseline, "REPO_ROOT", tmp_path)
    seen = []

    def fake_run(target, *_a):
        seen.append(target)
        return baseline.TargetResult(target, 0, 0.0, {"passed": 1}, "", [])

    monkeypatch.setattr(baseline, "run_isolated", fake_run)
    assert baseline.main(["--failing-from", *map(str, files)]) == 0
    # Deduped, order kept, flaky files and passing targets not rerun.
    assert seen == ["tests/a/test_x.py", "tests/a/test_slow.py", "tests/c/test_z.py"]


def test_failing_from_with_nothing_failing_runs_nothing(baseline, tmp_path, monkeypatch, capsys):
    ok = _write(baseline, tmp_path / "ok.json", baseline.TargetResult("tests/a", 0, 1.0, {}, "", []))
    monkeypatch.setattr(baseline, "run_isolated", lambda *_a: pytest.fail("nothing to rerun"))
    assert baseline.main(["--failing-from", str(ok)]) == 0
    assert "no failing files" in capsys.readouterr().err
