# devtonic-agent roadmap

The autonomous improvement loop works these items top-down. When an item lands, its PR checks it off and links to it.

## Phase 0: Perfect the fork (current)
- [x] Get a fast, reliable local test baseline: document which `scripts/run_tests.sh` targets pass on macOS and Linux, and record known-flaky tests in `docs/devtonic/test-baseline.md` (first slice: per-file baseline runner + macOS results, [#1](https://github.com/devtonic0/devtonic-agent/pull/1))
  - [x] Record the Linux column (run `scripts/devtonic/baseline.py` on `ubuntu-latest` / a Linux box) ([#2](https://github.com/devtonic0/devtonic-agent/pull/2), docs [#3](https://github.com/devtonic0/devtonic-agent/pull/3))
  - [x] Measure the large areas (`tests/agent`, `tests/tools`, `tests/gateway`, `tests/hermes_cli`, `tests/tui_gateway`) and add them to the baseline doc (macOS, `--set large --rerun-failed`, [#5](https://github.com/devtonic0/devtonic-agent/pull/5))
  - [x] Re-measure the large set with the messaging extras (`aiohttp`) installed, and record the Linux column (Linux, `devtonic-large.yml`, [#6](https://github.com/devtonic0/devtonic-agent/pull/6))
  - [ ] Triage the Linux large-set failures (`tests/hermes_cli` updater/source-build suites ~150, gateway 13 + 2 per-file timeouts, tools/agent collection errors)
    - [x] Find and fix harness artifacts: checkout-local `.venv` retargets `hermes update` tests, `-p no:cacheprovider` in argv breaks `test_relaunch` ([#7](https://github.com/devtonic0/devtonic-agent/pull/7))
    - [x] Re-measure the Linux large set with the fix and update the Linux table; rerun the failures in upstream's test env (`devtonic-triage.yml`, `--failing-from`, failure reasons) ([#8](https://github.com/devtonic0/devtonic-agent/pull/8))
    - [x] Bring the large workflow's env up to upstream's (`setup-pm` with the `tests.yml` extras, pnpm, ripgrep) so its Linux table reflects only real failures, and re-measure ([#9](https://github.com/devtonic0/devtonic-agent/pull/9))
    - [x] Report or fix the two Linux failures left in upstream's env (`test_runtime_self_protection.py` `/tmp` fixture overlap, `test_session_recovery_lost_and_found.py` host `sqlite3` CLI) ([#10](https://github.com/devtonic0/devtonic-agent/pull/10))
    - [ ] Offer both test fixes upstream (NousResearch/hermes-agent); the sqlite3 one applies to `persistence.sqlite.admin._lost_and_found` there
  - [x] Fix or mark the macOS-only failures in the large set (`/private/var` path compares, bash 3.2 pipeline status, real-home guard on host tools) ([#11](https://github.com/devtonic0/devtonic-agent/pull/11))
    - [x] Remaining macOS-only: 2 `tests/hermes_cli` real-home guard hits, Xvnc/xfce desktop test, launchd-vs-systemd service tests (mark `platforms("linux")` where Linux-only by design) ([#12](https://github.com/devtonic0/devtonic-agent/pull/12))
    - [ ] macOS leftovers outside those classes
      - [x] `uv run` venv `bin` on `PATH` in `test_session_client_env.py` (2), `test_readiness.py` degraded on a >90%-full host disk ([#13](https://github.com/devtonic0/devtonic-agent/pull/13))
      - [x] `sessions` store-holder gates in `tests/hermes_cli` (home-I/O guard refused the psutil holder scan's descriptor `stat`/`realpath` of a live gateway's files)
      - [ ] updater/autostash/recovery-closure and source-build/pnpm suites in `tests/hermes_cli` against the host toolchain
  - [ ] Triage the `tests/hermes_state` `messages_fts` malformed-schema failures on macOS / SQLite 3.53
- [ ] Expand Devtonic CI coverage step by step (core agent loop, tools, cron, cli) while keeping it under 15 minutes on `ubuntu-latest` (default baseline set already runs in CI, ~3 min, [#2](https://github.com/devtonic0/devtonic-agent/pull/2))
- [ ] Add a `scripts/devtonic/sync-upstream.sh` helper plus docs: merge upstream/main, run the baseline, open a PR
- [ ] Audit install: document a minimal clean install (`uv sync` + entrypoint) that doesn't touch `~/.hermes` of an existing upstream Hermes install (`DEVTONIC_HOME` / profile isolation)
- [ ] Identify and document every file path, env var, and CLI flag that Devtonic currently relies on (`hermes --cli -z`, `--continue`, `~/.hermes/logs/agent.log`, `cron/jobs.json`, `processes.json`), and add regression tests pinning them

## Phase 1: Embeddable API
- [ ] `devtonic/` package: stable Python API `run_turn(session, message) -> async iterator[Event]` wrapping the agent loop
- [ ] Event schema (`docs/devtonic/events.md`): `turn.start`, `thinking`, `tool.call`, `tool.result`, `message.delta`, `turn.end`, `error`
- [ ] `hermes serve --devtonic` local server: HTTP + WebSocket, token-auth, 127.0.0.1 only
- [ ] Sessions, cron, and config endpoints
- [ ] Version handshake endpoint (`/v1/info`) for host apps

## Phase 2: Devtonic integration
- [ ] devtonic-web Chat panel consumes the event stream instead of log tailing
- [ ] Installer: `devtonic-agent install` that Devtonic can call non-interactively

## Phase 3: Standalone app
- [ ] Spike: Tauri shell that bundles devtonic-web UI and launches the embedded agent server
- [ ] Packaging for macOS / Linux / Windows
