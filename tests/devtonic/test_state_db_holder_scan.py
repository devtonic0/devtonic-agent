"""The test home-I/O guard lets the state.db holder scan inspect other processes' descriptors.

On macOS the scan walks ``psutil`` ``open_files()`` and ``realpath()``s every path a
process holds. On a developer host running a live Hermes gateway those paths include the
real ``~/.hermes/logs/gateway.log`` and ``state.db``; the guard refused the read-only
metadata calls, the scan reported "open-file scan failed", and every ``hermes sessions``
store-holder gate test refused even after its holder exited. The guard now treats the scan
as descriptor inspection (like its ``/proc/<pid>/fd`` exemption) without loosening anything
outside it.
"""

from types import SimpleNamespace

import pytest

import hermes_state_holders

pytestmark = pytest.mark.platforms("macos")  # the psutil branch; Linux scans /proc


class _Proc:
    def __init__(self, pid, paths):
        self.info = {"pid": pid, "open_files": [SimpleNamespace(path=p) for p in paths]}


@pytest.fixture
def real_root():
    from tests.conftest import _REAL_HERMES_ROOT_CANDIDATES

    return min(_REAL_HERMES_ROOT_CANDIDATES)


def test_scan_completes_when_a_live_process_holds_files_under_the_real_home(monkeypatch, tmp_path, real_root):
    db_path = tmp_path / "state.db"
    db_path.write_bytes(b"")
    held = str(db_path.resolve()) + "-wal"
    processes = [
        _Proc(1001, [f"{real_root}/logs/gateway.log", f"{real_root}/state.db"]),
        _Proc(1002, [held]),
    ]
    monkeypatch.setattr(hermes_state_holders.psutil, "process_iter", lambda attrs: iter(processes))

    assert hermes_state_holders.foreign_state_db_holders(db_path) == [(1002, held)]


def test_guard_still_refuses_real_home_reads_after_a_scan(monkeypatch, tmp_path, real_root):
    monkeypatch.setattr(hermes_state_holders.psutil, "process_iter", lambda attrs: iter(()))
    hermes_state_holders.foreign_state_db_holders(tmp_path / "state.db")

    with pytest.raises(AssertionError, match="TEST BUG"):
        open(f"{real_root}/config.yaml")
