import io
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, call

import pytest

from scripts import instance, log_filter


def health_line(second=0, *, method="HEAD", path="/", status=200,
                origin="127.0.0.1", service="ollama-1", duration="23µs"):
    return (f'{service}  | [GIN] 2026/09/11 - 06:40:{second:02d} | {status} | '
            f'{duration} | {origin} | {method} "{path}"\n')


def render(events):
    output = io.StringIO()
    clock = Mock(return_value=0.0)

    def lines():
        for now, line in events:
            clock.return_value = now
            yield line

    log_filter.coalesce_logs(lines(), output, clock=clock)
    return output.getvalue()


def test_first_line_is_immediate_and_three_repeats_show_latest_timestamp():
    first = health_line()
    latest = health_line(30, duration="75µs")
    output = io.StringIO()
    clock = Mock(return_value=0.0)

    def lines():
        yield first
        assert output.getvalue() == first
        for second in (10, 20):
            clock.return_value = second
            yield health_line(second)
            assert output.getvalue() == first
        clock.return_value = 30
        yield latest
        assert output.getvalue() == first + latest.rstrip("\n") + (
            " [3 additional repeats in 30s; latest occurrence shown]\n"
        )

    log_filter.coalesce_logs(lines(), output, clock=clock)
    assert output.getvalue().count("additional repeats") == 1


def test_interleaved_health_keys_have_independent_counts_and_windows():
    heads = [health_line(second) for second in (0, 10, 20, 30)]
    posts = [health_line(second, method="POST", path="/api/show") for second in (1, 11, 21, 31)]
    events = [(second + offset, line) for second, pair in zip((0, 10, 20, 30), zip(heads, posts))
              for offset, line in enumerate(pair)]
    assert render(events) == (
        heads[0] + posts[0]
        + heads[-1].rstrip("\n") + " [3 additional repeats in 30s; latest occurrence shown]\n"
        + posts[-1].rstrip("\n") + " [3 additional repeats in 30s; latest occurrence shown]\n"
    )


@pytest.mark.parametrize("line", [
    health_line(status=500), health_line(status=400), health_line(status=404),
    health_line(status=201), health_line(status=204),
    health_line(method="POST", path="/api/generate"),
    health_line(method="POST", path="/api/chat"),
    health_line(method="POST", path="/api/embed"),
    health_line(method="POST", path="/api/embeddings"),
    health_line(method="HEAD", path="/api/show"), health_line(method="POST"),
    health_line(method="GET"), health_line(path="/?probe=1"),
    health_line(method="POST", path="/api/show?model=x"),
    health_line(origin="172.18.0.3"), health_line(origin="127.0.0.10"),
    health_line(service="bot-1"), health_line(service="ollama-pull-1"),
    health_line().rstrip("\n") + " ERROR: model unavailable\n",
    "ollama-1 | runner crashed\n", "Error response from daemon: unavailable\n",
    "bot-1 | ordinary message\n", "Traceback (most recent call last):\n",
    "\n", "unmatched final line without newline",
])
def test_every_other_line_is_unchanged_and_immediate(line):
    first = health_line()
    repeat = health_line(1)
    output = io.StringIO()
    clock = Mock(return_value=0.0)

    def lines():
        yield first
        clock.return_value = 1
        yield repeat
        yield line
        assert output.getvalue() == first + line
        yield line
        assert output.getvalue() == first + line + line

    log_filter.coalesce_logs(lines(), output, clock=clock)
    assert output.getvalue().startswith(first + line + line)
    assert output.getvalue().endswith(" [1 additional repeats in 1s; latest occurrence shown]\n")


def test_colored_compose_prefix_and_gin_fields_keep_original_latest_line():
    first = health_line(service="maxwell-curie-ollama-1")
    first = first.replace("maxwell-curie-ollama-1", "\x1b[36mmaxwell-curie-ollama-1\x1b[0m")
    latest = health_line(30, service="maxwell-curie-ollama-1")
    latest = latest.replace("maxwell-curie-ollama-1", "\x1b[1;36mmaxwell-curie-ollama-1\x1b[0m")
    latest = latest.replace("200", "\x1b[97;42m200\x1b[0m")
    assert render([(0, first), (30, latest)]) == (
        first + latest.rstrip("\n") + " [1 additional repeats in 30s; latest occurrence shown]\n"
    )


def test_service_and_local_origin_are_separate_keys():
    lines = [health_line(), health_line(service="ollama-2"), health_line(origin="::1")]
    result = render([(0, line) for line in lines] + [(10, line) for line in lines])
    assert result.startswith("".join(lines))
    assert result.count("[1 additional repeats in 10s; latest occurrence shown]") == 3


def test_unrelated_next_line_flushes_expired_summary_without_hiding_itself():
    first, repeat = health_line(), health_line(10)
    unrelated = "bot-1 | still working\n"
    assert render([(0, first), (10, repeat), (30, unrelated)]) == (
        first + repeat.rstrip("\n") + " [1 additional repeats in 30s; latest occurrence shown]\n"
        + unrelated
    )


def test_late_health_line_starts_new_window_instead_of_extending_old_one():
    first, repeat, late = health_line(), health_line(10), health_line(40)
    assert render([(0, first), (10, repeat), (40, late)]) == (
        first + repeat.rstrip("\n") + " [1 additional repeats in 30s; latest occurrence shown]\n"
        + late
    )


def test_end_flushes_pending_repeats_once_but_not_singletons():
    first, repeat = health_line(), health_line(10)
    post = health_line(20, method="POST", path="/api/show")
    assert render([(0, first), (10, repeat), (20, post)]) == (
        first + post + repeat.rstrip("\n")
        + " [1 additional repeats in 20s; latest occurrence shown]\n"
    )
    assert render([]) == ""
    assert render([(0, first)]) == first


def test_interrupt_flushes_pending_summary_before_propagating():
    output = io.StringIO()
    clock = Mock(return_value=0.0)
    first, repeat = health_line(), health_line(10)

    def lines():
        yield first
        clock.return_value = 10
        yield repeat
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        log_filter.coalesce_logs(lines(), output, clock=clock)
    assert output.getvalue() == (
        first + repeat.rstrip("\n") + " [1 additional repeats in 10s; latest occurrence shown]\n"
    )


def test_actual_logs_action_delegates_without_lifecycle_mutations(monkeypatch):
    app = instance.Instance.__new__(instance.Instance)
    app.project = "maxwell-fixture"
    app.env = {"DOCKER_HOST": "unix:///synthetic/docker.sock"}
    app.inventory = Mock(return_value=[])
    app.docker = Mock(side_effect=AssertionError("no lifecycle mutation"))
    follower = Mock()
    monkeypatch.setattr(log_filter, "follow_logs", follower)
    instance.lifecycle(app, "logs")
    app.inventory.assert_called_once_with()
    app.docker.assert_not_called()
    command, env = follower.call_args.args
    assert command == ["docker", "compose", "--project-name", app.project,
                       "--project-directory", str(instance.CHECKOUT), "--env-file", "/dev/null",
                       "-f", str(instance.CHECKOUT / "compose.yaml"),
                       "logs", "--follow", "--tail", "100"]
    assert env is app.env


def test_standalone_help_does_not_require_log_filter(tmp_path):
    script = tmp_path / "instance.py"
    script.write_bytes(Path(instance.__file__).read_bytes())
    result = subprocess.run(
        [sys.executable, "-B", "-E", "-s", str(script), "--help"],
        cwd=tmp_path, env={"HOME": str(tmp_path), "PATH": "/usr/local/bin:/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "logs" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("interrupted,returncode", [(False, 0), (False, 7), (True, 0)])
def test_follower_streams_and_reaps_only_its_child_group(monkeypatch, interrupted, returncode):
    process = Mock(pid=12345, stdout=io.StringIO("bot-1 | hello\n"))
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.wait.return_value = returncode
    popen = Mock(return_value=process)
    killpg = Mock()
    stream = Mock(side_effect=KeyboardInterrupt if interrupted else None)
    monkeypatch.setattr(log_filter.subprocess, "Popen", popen)
    monkeypatch.setattr(log_filter.os, "killpg", killpg)
    monkeypatch.setattr(log_filter, "coalesce_logs", stream)
    command, env = ["docker", "compose", "logs", "--follow"], {"DOCKER_HOST": "synthetic"}
    if returncode:
        with pytest.raises(RuntimeError, match="Compose command failed"):
            log_filter.follow_logs(command, env)
    else:
        log_filter.follow_logs(command, env)
    popen.assert_called_once_with(command, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                  errors="surrogateescape", start_new_session=True)
    stream.assert_called_once_with(process.stdout, sys.stdout)
    assert killpg.call_args_list == [call(12345, signal.SIGTERM), call(12345, signal.SIGKILL)]
    assert process.wait.call_args_list[-2:] == [call(timeout=5), call()]
    process.__exit__.assert_called_once()


def test_stubborn_follower_is_killed_and_reaped_without_waiting_in_test(monkeypatch):
    process = Mock(pid=12345, stdout=io.StringIO())
    process.__enter__ = Mock(return_value=process)
    process.__exit__ = Mock(return_value=False)
    process.wait.side_effect = [subprocess.TimeoutExpired("logs", 5), -signal.SIGKILL]
    killpg = Mock()
    monkeypatch.setattr(log_filter.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(log_filter.os, "killpg", killpg)
    monkeypatch.setattr(log_filter, "coalesce_logs", Mock(side_effect=KeyboardInterrupt))
    log_filter.follow_logs(["docker", "compose", "logs"], {})
    assert killpg.call_args_list == [call(12345, signal.SIGTERM), call(12345, signal.SIGKILL)]
    assert process.wait.call_args_list == [call(timeout=5), call()]
