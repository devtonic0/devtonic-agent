# Local test baseline

A fast, reliable set of test targets for the devtonic-agent fork, how to run
them, and which areas are known to fail or flake on which host.

## Running it

```bash
uv sync --group dev --group test
uv run python scripts/devtonic/baseline.py                 # default fast set (~2 min)
uv run python scripts/devtonic/baseline.py tests/cron      # explicit targets
uv run python scripts/devtonic/baseline.py --json out.json # machine-readable results
uv run python scripts/devtonic/baseline.py tests/x -- -k foo   # args after -- go to pytest
uv run python scripts/devtonic/baseline.py --set large --rerun-failed  # large areas, flakes split out (~45 min)
uv run python scripts/devtonic/baseline.py --failing-from large.json  # rerun only the files that failed there
```

Results JSON carries each failure's one-line pytest reason (`reasons`, node id
→ `AssertionError: ...`), and `--markdown` prints it next to the node id, so a
CI artifact is enough to sort failures by cause.

For `--set large`, put the env outside the checkout
(`UV_PROJECT_ENVIRONMENT=/some/other/path uv sync ...` and the same variable on
`uv run`): the `hermes update` suites misbehave under a checkout-local `.venv`
(see the triage section below).

- Each **test file** runs in its own `python -m pytest` subprocess (the same
  isolation unit as upstream's `scripts/run_tests.sh` /
  `scripts/run_tests_parallel.py`), up to `-j` files in parallel. Running a whole
  directory in one process leaks module state between files and produces false
  failures — e.g. `tests/providers` shows 19 failures in one process and 0 per
  file. `--per-dir` restores the single-process mode for debugging.
- Like `run_tests.sh`, the child environment is rebuilt from an allowlist
  (`PATH`, `HOME`, `TMPDIR`, cert locations, CI flags, test-runner knobs);
  `HERMES_HOME`, `HERMES_RUNTIME_DIR`, `PYTHONPATH` and credentials never reach
  the tests. `TZ=UTC`, `LANG=C.UTF-8` and `PYTHONHASHSEED=0` are pinned.
  `tests/conftest.py` sandboxes `HERMES_HOME` and fences the network, so the
  baseline never touches a real `~/.hermes` install.
- `scripts/run_tests.sh` remains the CI-parity runner; it needs the
  `pm.build_env` test interpreter (see `tests/AGENTS.md`). `baseline.py` only
  needs the repo's `uv` environment.

## Default targets (must stay green)

Measured on macOS 15.5 arm64, Python 3.14.6 (uv-managed), SQLite 3.53.4:

| Target | Status | Passed | Failed | Errors | Skipped | Time (s) |
|---|---|---|---|---|---|---|
| `tests/devtonic` | pass | 7 | 0 | 0 | 0 | 1 |
| `tests/hermes_platform` | pass | 122 | 0 | 0 | 5 | 2 |
| `tests/conformance` | pass | 15 | 0 | 0 | 6 | 24 |
| `tests/providers` | pass | 93 | 0 | 0 | 0 | 23 |
| `tests/skills` | pass | 1567 | 0 | 0 | 1 | 14 |
| `tests/cron` | pass | 1594 | 0 | 0 | 11 | 63 |

Linux, Devtonic CI `test` job (`ubuntu-latest` = Ubuntu 26.04 image
20261101.186.1, x86_64, system CPython 3.14.4), run
[42559722653](https://github.com/devtonic0/devtonic-agent/actions/runs/42559722653):

| Target | Status | Passed | Failed | Errors | Skipped | Time (s) |
|---|---|---|---|---|---|---|
| `tests/devtonic` | pass | 8 | 0 | 0 | 0 | 1 |
| `tests/hermes_platform` | pass | 121 | 0 | 0 | 6 | 2 |
| `tests/conformance` | pass | 19 | 0 | 0 | 2 | 23 |
| `tests/providers` | pass | 93 | 0 | 0 | 0 | 23 |
| `tests/skills` | pass | 1567 | 0 | 0 | 1 | 12 |
| `tests/cron` | pass | 1603 | 0 | 0 | 2 | 97 |

Skip counts differ by host because some tests are gated with
`@pytest.mark.platforms(...)` (e.g. 9 cron tests and 4 conformance tests that
skip on macOS run on Linux). The whole Devtonic CI job takes about 3 minutes.

## In CI

The Devtonic CI `test` job runs the default set on every PR and on pushes to
`main`:

```bash
uv run python scripts/devtonic/baseline.py --json baseline-linux.json --markdown "$GITHUB_STEP_SUMMARY"
```

The host line and results table show up on the run's summary page, and the JSON
is uploaded as the `baseline-linux` artifact. `--markdown` appends to the target
file, so it is safe to use with `$GITHUB_STEP_SUMMARY`. A failure in any default
target fails the required `test` check.

## Opt-in targets

| Target | How to run | macOS result |
|---|---|---|
| `tests/acp_adapter` | `uv run --extra acp python scripts/devtonic/baseline.py tests/acp_adapter` | pass (421 passed, 37 skipped, 28 s) |
| `tests/monitoring` | default env | pass (19 passed, 2 skipped) |

`tests/acp_adapter` needs the `acp` extra (`agent-client-protocol`); without it
every file fails at import with `ModuleNotFoundError: No module named 'acp'`.
Note `uv run --extra acp` re-syncs the venv; a later plain `uv run` removes the
extra again.

## Known failures

| Target | Host | Result | Symptom |
|---|---|---|---|
| `tests/hermes_state` | macOS 15.5, Py 3.14.6, SQLite 3.53.4 | 68 failed / 1761 passed across 22 files | `sqlite3.DatabaseError: malformed database schema (messages_fts) - table messages_fts already exists` in the state.db repair / FTS rebuild / auto-vacuum paths (`test_state_db_malformed_repair.py`, `test_state_db_repair_non_destructive.py`, `test_hermes_state.py::TestVacuum`/`TestAutoMaintenance`, ...). Deterministic, not flaky. Suspected interaction with the newer bundled SQLite; untriaged. |

## Known flaky

None observed yet in the default set (two consecutive per-file runs were
identical). Record flakes here with host, file and symptom as they show up.

## Large areas (`--set large`)

These five areas hold most of the upstream suite (about 6,000 test files).
They are not in CI. Run them explicitly:

```bash
uv run python scripts/devtonic/baseline.py --set large --rerun-failed --json large.json
```

`--rerun-failed` reruns each failing file on its own, serially. Files that pass
alone are reported as `flaky` (they failed only under `-j` parallel load), and
the target only stays `fail` if a file fails again in isolation.

Measured on macOS 15.5 arm64, Python 3.14.6, SQLite 3.53.4, 11 CPUs, `-j 8`,
default `uv sync --group dev --group test` environment:

| Target | Status | Passed | Failed | Errors | Skipped | Time (s) |
|---|---|---|---|---|---|---|
| `tests/tui_gateway` | fail | 3128 | 6 | 7 | 13 | 208 |
| `tests/tools` | fail | 11040 | 25 | 1 | 353 | 367 |
| `tests/agent` | fail | 12451 | 7 | 1 | 65 | 458 |
| `tests/gateway` | fail | 12235 | 209 | 112 | 349 | 775 |
| `tests/hermes_cli` | fail | 18799 | 132 | 6 | 685 | 852 |

The whole set takes about 44 minutes. That is 57,653 passing tests, and about
0.9% fail or error. Every failing file was rerun alone to classify it:

| Cause | Where | Files |
|---|---|---|
| Optional deps missing from the `dev`+`test` groups: `aiohttp` (messaging extras), `acp`, `keyring`, `fal_client` | gateway (143 + ~11 that patch `aiohttp` attrs), tools 4, tui_gateway 7, agent 2, hermes_cli 3 | ~170 |
| macOS `/var` → `/private/var` tmp symlink: paths compared unresolved | `tests/agent/test_compaction_prompt_rebuild.py` (3), `tests/tools/test_delegate.py` (1), `tests/gateway/test_session_client_env.py` | 3 |
| Real-home I/O guard trips on host tools outside the sandbox (e.g. a `node` found in `~/.local/bin`) | `tests/tui_gateway/test_profiles_list_*` (6), 2 in `tests/hermes_cli` | 5 |
| Linux-only tooling assumed: Xvnc/xfce desktop, GNU bash ≥ 4 (`PIPESTATUS` / `pipefail` exit codes under macOS bash 3.2), launchd vs systemd service paths | `tests/tools/test_bot_desktop_resources.py`, `tests/tools/test_terminal_pipeline_status.py` (4), gateway restart/launchd tests, hermes_cli service tests | ~10 |
| No managed llama.cpp server discovered on macOS | `tests/agent/test_llamacpp_alias_managed_endpoint.py` (2) | 1 |
| Session-group daemon start timeouts (`timed out after 30s waiting for groups.capabilities`) | `tests/gateway/test_session_group_peer_*` | 3 |
| Other deterministic assertion failures (API authority, readiness, WhatsApp adapters, updater/desktop build stamps, the repo `.venv` warning) | gateway ~20, hermes_cli ~30, tools 2 | ~50 |

Flaky under parallel load, passed when rerun alone:
`tests/agent/test_cascading_interrupt.py`, `tests/agent/test_subdirectory_hints.py`,
`tests/tools/test_patch_multimatch_locations.py`,
`tests/tui_gateway/test_busy_compression_demotion.py`,
`tests/hermes_cli/test_dashboard_session_token_file.py`,
`tests/hermes_cli/test_gateway_launch_lifetime.py`,
`tests/hermes_cli/test_kanban_worker_pid_fingerprint.py`,
`tests/hermes_cli/test_source_build.py`.

Most of the macOS gateway failures come from the missing `aiohttp`.

### Linux column (messaging extras installed)

`.github/workflows/devtonic-large.yml` runs the same set on `ubuntu-latest`,
one job per area, with `uv sync --group dev --group test --extra messaging`,
`--rerun-failed --timeout 300` (per file). It runs on `workflow_dispatch` and on
PRs that touch the workflow file, and is not a required check. The `summary` job merges the per-area JSON with
`baseline.py --merge-json` into a `large-linux` artifact.

Measured on `ubuntu-latest` (4 CPUs) after the harness fix in
[#7](https://github.com/devtonic0/devtonic-agent/pull/7), run
[44458042669](https://github.com/devtonic0/devtonic-agent/actions/runs/44458042669).
The #7 fix: the large workflow keeps the uv env outside the checkout
(`UV_PROJECT_ENVIRONMENT`), because `hermes_cli/update_owning_install.py`
treats a checkout-local `venv`/`.venv` as the install's own interpreter and
points every updater test at the repo instead. `baseline.py` also passes
`-p no:cacheprovider` via `PYTEST_ADDOPTS`, because `test_relaunch.py`
compares the child's `sys.argv`.

| Target | Status | Passed | Failed | Errors | Skipped | Time (s) |
|---|---|---|---|---|---|---|
| `tests/tui_gateway` | pass | 3176 | 0 | 0 | 1 | 549 |
| `tests/tools` | fail | 11271 | 5 | 1 | 181 | 803 |
| `tests/agent` | fail | 12472 | 2 | 1 | 49 | 1000 |
| `tests/gateway` | timeout | 13656 | 11 | 0 | 81 | 2640 |
| `tests/hermes_cli` | fail | 19144 | 27 | 54 | 429 | 1217 |

59,719 passing tests (up from 59,649 before the fix). `tests/hermes_cli` drops
from 149 failures/errors to 81, and the files that went fully green are
`test_commit_build_cli.py`, `test_relaunch.py`, `test_source_release_channels.py`,
`test_update_autostash.py`, `test_update_channel.py`,
`test_update_fleet_restart_pending.py`, `test_update_head_moved_gate.py`,
`test_update_parked_branch_guard.py`, `test_update_target_identity.py` (31),
`test_update_venv_holder_retirement.py`. So the bare-`.git` damage check in
`test_update_autostash.py` / `test_update_fleet_restart_pending.py` seen on
macOS does not reproduce on Linux (git 2.56 vs Apple git 2.39). Gateway is
unchanged apart from `test_update_streaming.py` going green.

#### Triage of what remains: environment, not product bugs

The large workflow's thin env (`uv sync --group dev --group test --extra
messaging`, system git/no pnpm/no ripgrep) is not the env upstream tests in.
`.github/workflows/devtonic-triage.yml` reruns only the failing files from a
large run's `large-linux` artifact (`baseline.py --failing-from`) in upstream's
own test env, the same setup as `.github/workflows/tests.yml`: the `setup-pm` action
(PM-pinned Python with a SQLite that does not have the WAL-reset bug, the
`all`/`fal`/`keychain`/... extras, pnpm + Node), and ripgrep 15.1. It takes
about 5 minutes instead of 55. Run
[44567583336](https://github.com/devtonic0/devtonic-agent/actions/runs/44567583336):
**33 of the 35 failing files pass**, including both gateway files that timed
out at 300 s (`test_legacy_desktop_source.py`, `test_route_transition_racing_turn.py`
pass in 2 s).

Each failure's short reason is now in the JSON (`reasons`), and that is how
these were sorted:

| Cause in the thin env | Files |
|---|---|
| Missing extras: `acp` (`agent-client-protocol`), `keyring`, `fal_client` | gateway `test_model_confirmation_clients.py`, `test_session_edit_policy.py`, `test_session_mutation_model.py`, `test_session_policy_refusal_fields.py`; `test_gateway_client_recovery_backlog.py`, `test_conversation_compression_manual.py[acp]`, `test_vault_key_*.py`, `test_fal_sdk.py` |
| No `pnpm` on PATH (`source-build integration requires node and pnpm`) | `test_source_build.py` (13), `test_tui_npm_install.py` (7), `test_web_ui_build.py` (6), `test_desktop_source_build.py` (3) |
| No `rg` on PATH | `test_doctor_pm_store_probe.py` (8), `tools/test_search_*` (5) |
| uv's system CPython links SQLite 3.46.1, which has the WAL-reset bug, so Hermes picks DELETE mode and extra repair/warning paths fire | `test_update_finish.py` (16), `test_update_post_commit_safety.py` (2, extra `sqlite_runtime` follow-up), `test_doctor_structural_corruption.py`, `test_watch_notification_reset_pin.py` |
| Runner env leaks into the tests: with the caller's full env, kanban dispatch decides it must create a restart-safe systemd scope (`cannot create restart-safe systemd scope ... no current run id`), and the service-choice tests hit the runner's real `~/.config/systemd/user`. Both pass once the child env is reduced to `run_tests.sh`'s allowlist; which forwarded variable triggers the systemd path was not isolated | 6 kanban worker-spawn files (8 tests), `test_kanban_multiplex_served_profile_parity.py`, `test_gateway_service_choice.py` |
| Fail alone in the thin env but pass in upstream's env, cause not isolated (likely the DELETE-mode SQLite above: lock contention and slower writes) | `test_claim_reopen_off_loop.py` (owner loop stalled 1.01 s), the two 300 s timeouts |

The systemd and `HERMES_HOME` leaks are why `baseline.py` now builds the
pytest child's environment like `scripts/run_tests.sh` (`env -i` plus an
allowlist: `PATH`, `HOME`, `TMPDIR`, cert locations, CI flags, test-runner
knobs). The first triage pass inherited `setup-pm`'s exported `HERMES_HOME`
and tripped the tests' real-home guard in 31 tests.

Still failing in upstream's env, both reproducible alone:

- `tests/agent/test_runtime_self_protection.py::test_find_delete_over_own_venv_is_detected`:
  the negative case `find /tmp -name __pycache__ -delete` is expected to be
  allowed, but the fixture builds the fake runtime under pytest's `tmp_path`,
  which is under `/tmp` on Linux. So that `find` really does cover the
  protected venv and gets flagged. The product behaves correctly, and the test
  is host-dependent. It passes on macOS, where `tmp_path` is under
  `/private/var/folders`. Fix candidate for upstream: use a sibling path of the
  fixture instead of the literal `/tmp`.
- `tests/hermes_cli/test_session_recovery_lost_and_found.py::test_unreadable_schema_without_cli_names_the_sqlite3_requirement`:
  host-tool dependent. The test expects the "no usable sqlite3 CLI" message to
  name `.recover`, but the host's `sqlite3` CLI (Ubuntu and macOS) is found and
  judged unsafe, which produces a different message. Fails on macOS too.

macOS rerun of the same 35 files (`--failing-from`, messaging extra, env outside
the checkout, uv's Python with SQLite 3.53): 19 pass. The remainder are the macOS
classes already listed above (missing `acp`/`keyring`/`fal_client`, the
real-home guard on a host `node`, `/var` → `/private/var`), plus
`test_update_recovery_closure.py` (8) and the pnpm-driven source-build tests
running against the host's nvm Node. `test_update_recovery_closure.py` passes on
Linux in upstream's env.

## Not yet measured

`tests/e2e`, `tests/integration`, `tests/pm`, `tests/plugins`.
