"""The bash wrapper reports each pipeline segment's own exit status."""

import subprocess

import pytest

from tools.environments.base_session_env import _split_cwd_marker, _wrap_command_script

CWD_MARKER = "__HERMES_CWD_test__"
PIPE_MARKER = "__HERMES_PIPE_test__"


def _script(command: str, pipe_marker: str = PIPE_MARKER) -> str:
    return _wrap_command_script(
        command, quoted_cwd="/tmp", quoted_snap="/nonexistent-snapshot",
        snap_tmp_template="/tmp/hermes-snap.XXXXXX", passthrough_names=(),
        snapshot_ready=False, cwd_marker=CWD_MARKER, pipe_marker=pipe_marker,
    )


def _run_result(command: str, pipe_marker: str = PIPE_MARKER) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", _script(command, pipe_marker)], capture_output=True, text=True, check=False,
    )


def _run(command: str) -> str:
    return _run_result(command).stdout


def _bash_major() -> int:
    out = subprocess.run(["bash", "-c", "echo ${BASH_VERSINFO[0]}"], capture_output=True, text=True, check=False)
    return int(out.stdout.strip() or 0)


# bash 3.2 (macOS /bin/bash) reports an eval'd syntax error as 1, not 2, and drops a trailing
# backslash-newline continuation's backslash: the shell's own semantics, not the wrapper's.
_needs_bash4 = pytest.mark.skipif(_bash_major() < 4, reason="bash >= 4 syntax-error / line-continuation semantics")


def test_pipeline_status_captures_the_leading_command():
    output = _run("false | true")

    assert f"{PIPE_MARKER}1 0{PIPE_MARKER}" in output


def test_plain_command_reports_one_status():
    output = _run("false")

    assert f"{PIPE_MARKER}1{PIPE_MARKER}" in output


def _seen(result: subprocess.CompletedProcess) -> tuple[int, str, str]:
    """Exit code and output as the model sees them, markers stripped like production does."""
    stdout = result.stdout
    for marker in (PIPE_MARKER, CWD_MARKER):
        split = _split_cwd_marker(stdout, marker)
        stdout = split[1] if split else stdout
    return result.returncode, stdout, result.stderr


@pytest.mark.parametrize(
    ("command", "exit_code", "stdout"),
    [
        ("if false; then echo yes; fi", 0, ""),
        ("while read line; do echo \"$line\"; done < /dev/null", 0, ""),
        ("set -o pipefail; false | true", 1, ""),
        ("! false", 0, ""),
        ("! true", 1, ""),
        pytest.param("echo 'unbalanced", 2, "", marks=_needs_bash4),
        pytest.param('echo "unbalanced', 2, "", marks=_needs_bash4),
        pytest.param("echo $(echo unclosed", 2, "", marks=_needs_bash4),
        pytest.param("echo hi \\", 0, "hi \\\n", marks=_needs_bash4),
        ("cat <<'EOF'\nunterminated heredoc", 0, "unterminated heredoc\n"),
        ("exit 3", 3, ""),
        ("trap 'echo T' ERR; false", 1, "T\n"),
    ],
)
def test_capturing_pipestatus_changes_nothing_the_model_sees(command, exit_code, stdout):
    """The capture is side data: the shell's own ``$?`` and output, no wrapper text."""
    seen_code, seen_stdout, seen_stderr = _seen(_run_result(command))

    assert (seen_code, seen_stdout) == (exit_code, stdout)
    assert "__hermes" not in seen_stderr
