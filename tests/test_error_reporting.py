import asyncio
import io
import json
import logging
import multiprocessing
import os
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

import error_reporting as reporting
from error_reporting import (
    PUBLIC_ERROR_TEXT,
    IncidentLoggingHandler,
    IncidentStorageError,
    IncidentStore,
    capture_incident,
    configure_incident_store,
    get_incident_store,
    incident_context,
    register_secrets,
)


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    monkeypatch.setattr(reporting, "_store", None)
    monkeypatch.setattr(reporting, "_secrets", ())


def process_records(path: Path, number: int, count: int, barrier) -> None:
    store = IncidentStore(path)
    barrier.wait(timeout=15)
    for index in range(count):
        store.record("synthetic.process", f"{number}:{index}")


def test_public_text_and_configuration_do_not_create_files(tmp_path):
    assert PUBLIC_ERROR_TEXT == "I waited, waited and I am losing things like tears in the rain 🕊️"
    assert get_incident_store() is None
    assert capture_incident("unconfigured", "synthetic") is None
    path = tmp_path / "not-created" / "history.json"
    store = configure_incident_store(path, secrets=["synthetic-configured-credential"])
    assert get_incident_store() is store
    assert not path.parent.exists()
    assert store.last_error is None


def test_global_order_and_eviction_across_scopes(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    ids = []
    for index in range(14):
        with incident_context(channel=str(index), guild="dm" if index % 2 else "server"):
            ids.append(capture_incident("synthetic", str(index)))
    assert len(set(ids)) == 14
    assert [store.get(index).summary for index in range(10)] == [str(i) for i in range(13, 3, -1)]
    assert store.get(0).context == {"channel": "13", "guild": "dm"}
    assert store.get(-1) is None
    assert store.get(10) is None
    assert store.get(100) is None


def test_reload_and_immutable_snapshot(tmp_path):
    path = tmp_path / "history.json"
    store = IncidentStore(path)
    context = {"channel": "channel-one", "user": "synthetic-user"}
    incident_id = store.record("provider", "upstream rejected 🕊️", details="complete body", context=context)
    snapshot = store.get(0)
    context["channel"] = "changed-outside"
    assert snapshot.context["channel"] == "channel-one"
    with pytest.raises(FrozenInstanceError):
        snapshot.summary = "mutated"
    with pytest.raises(TypeError):
        snapshot.context["channel"] = "mutated"
    reloaded = IncidentStore(path).get(0)
    assert reloaded == snapshot
    assert reloaded.incident_id == incident_id
    assert datetime.fromisoformat(reloaded.timestamp).utcoffset() == UTC.utcoffset(None)
    assert set(json.loads(path.read_text())["incidents"][0]) == {
        "incident_id", "timestamp", "source", "summary", "traceback", "details", "context",
    }


def test_full_body_exception_chain_and_provider_diagnostics(tmp_path):
    store = IncidentStore(tmp_path / "history.json")
    body = "upstream explanation\n" * 12000 + "BODY-END"
    try:
        try:
            raise ValueError("inner transport explanation")
        except ValueError as cause:
            cause.incident_details = "status=502 request_id=request-preserved\n" + body
            raise RuntimeError("outer provider failed") from cause
    except RuntimeError as exception:
        store.record("provider", "synthetic failure", exception=exception, details="boundary diagnostics")
    incident = store.get(0)
    report = incident.format_report()
    assert body in incident.details
    assert "boundary diagnostics" in incident.details
    assert "status=502 request_id=request-preserved" in report
    assert "ValueError: inner transport explanation" in incident.traceback
    assert "RuntimeError: outer provider failed" in incident.traceback
    assert "direct cause" in incident.traceback
    assert "test_full_body_exception_chain_and_provider_diagnostics" in report
    assert "BODY-END" in IncidentStore(store.path).get(0).format_report()


def test_exception_groups_are_not_width_or_depth_truncated(tmp_path):
    exception = ExceptionGroup("wide", [ValueError(f"leaf-{i}") for i in range(25)])
    for index in range(14):
        exception = ExceptionGroup(f"nested-{index}", [exception])
    store = IncidentStore(tmp_path / "history.json")
    store.record("groups", "all members", exception=exception)
    report = store.get(0).traceback
    assert "leaf-24" in report
    assert "leaf-0" in report
    assert "max_group_depth" not in report
    assert "and 10 more exceptions" not in report


def test_distinct_equal_text_exceptions_do_not_coalesce(tmp_path):
    store = IncidentStore(tmp_path / "history.json")
    first = store.record("provider", "identical", exception=ValueError("identical"))
    second = store.record("provider", "identical", exception=ValueError("identical"))
    assert first != second
    assert store.get(0).incident_id == second
    assert store.get(1).incident_id == first


def test_propagated_exception_updates_original_without_new_slot(tmp_path):
    store = IncidentStore(tmp_path / "history.json")
    cause = ValueError("inner")
    first = store.record("provider", "first", exception=cause, details="full original body")
    snapshot = store.get(0)
    newer = store.record("unrelated", "newer")
    try:
        raise RuntimeError("wrapper") from cause
    except RuntimeError as exception:
        second = store.record("outer", "second", exception=exception, details="outer details", context={"message": "m"})
        assert exception.incident_id == first
    assert second == first == cause.incident_id
    assert store.get(0).incident_id == newer
    merged = store.get(1)
    assert merged.timestamp == snapshot.timestamp
    assert merged.source == "provider"
    assert "full original body" in merged.details
    assert "outer details" in merged.details
    assert "Source: outer" in merged.details
    assert "Summary: second" in merged.details
    assert merged.context["message"] == "m"
    assert store.get(2) is None
    assert snapshot.details == "full original body"


def test_suppressed_exception_context_still_groups_private_diagnostics(tmp_path):
    store = IncidentStore(tmp_path / "history.json")
    try:
        try:
            raise ValueError("suppressed provider cause")
        except ValueError as cause:
            cause.incident_details = "suppressed full provider body"
            first = store.record("provider", "caught", exception=cause)
            raise RuntimeError("public wrapper") from None
    except RuntimeError as exception:
        assert store.record("outer", "wrapper", exception=exception) == first
    report = store.get(0).format_report()
    assert "ValueError: suppressed provider cause" in report
    assert "RuntimeError: public wrapper" in report
    assert "suppressed full provider body" in report
    assert store.get(1) is None


def test_same_exception_concurrently_uses_one_slot_across_store_objects(tmp_path):
    path = tmp_path / "history.json"
    exception = RuntimeError("one exception")
    barrier = threading.Barrier(8)

    def record(index):
        barrier.wait(timeout=15)
        return IncidentStore(path).record("thread", str(index), exception=exception, details=f"detail-{index}")

    with ThreadPoolExecutor(max_workers=8) as executor:
        ids = list(executor.map(record, range(8)))
    assert len(set(ids)) == 1
    store = IncidentStore(path)
    assert store.get(1) is None
    for index in range(8):
        assert f"detail-{index}" in store.get(0).details


def test_threads_do_not_lose_distinct_writes(tmp_path):
    path = tmp_path / "history.json"
    barrier = threading.Barrier(8)

    def record(index):
        barrier.wait(timeout=15)
        return IncidentStore(path).record("thread", str(index))

    with ThreadPoolExecutor(max_workers=8) as executor:
        ids = list(executor.map(record, range(8)))
    store = IncidentStore(path)
    assert {store.get(i).incident_id for i in range(8)} == set(ids)
    assert store.get(8) is None


@pytest.mark.parametrize("count", [2, 5])
def test_process_writes_are_locked_and_retained(tmp_path, count):
    path = tmp_path / "history.json"
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(4)
    processes = [context.Process(target=process_records, args=(path, i, count, barrier)) for i in range(4)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.kill()
                process.join(timeout=10)
    store = IncidentStore(path)
    incidents = [store.get(i) for i in range(min(count * 4, 10))]
    assert len({item.incident_id for item in incidents}) == min(count * 4, 10)
    summaries = {item.summary for item in incidents}
    expected = {f"{i}:{j}" for i in range(4) for j in range(count)}
    assert summaries <= expected
    if count == 2:
        assert summaries == expected
    assert store.get(min(count * 4, 10)) is None


def test_known_secrets_redact_every_capture_field_and_disk(tmp_path):
    secret = "synthetic-configured-credential"
    register_secrets([secret, "", secret + "-longer"])
    store = IncidentStore(tmp_path / "history.json")
    try:
        raise RuntimeError(f"provider rejected {secret}")
    except RuntimeError as exception:
        exception.incident_details = f"provider diagnostic {secret}-longer END"
        store.record(secret, f"summary {secret}", exception=exception, details=f"body {secret}", context={secret: secret})
    report = store.get(0).format_report()
    assert secret not in report
    assert "[REDACTED]-longer" not in report
    assert "[REDACTED]" in report
    assert secret not in store.path.read_text()
    assert "END" in report


def test_sensitive_material_is_removed_without_erasing_diagnostics(tmp_path):
    details = (
        'Authorization: Bearer synthetic-header-value\n'
        'Proxy-Authorization: Basic synthetic-proxy-value\n'
        'Cookie: session=synthetic-cookie-value; other=synthetic-cookie-two\n'
        'Set-Cookie: session=synthetic-response-cookie; HttpOnly\n'
        '{"Authorization": "Bearer synthetic-json-value", "status": 403}\n'
        "{'cookie': 'synthetic-dict-cookie', 'request_id': 'request-visible'}\n"
        '{"api_key": "synthetic-body-key", "message": "explanation preserved"}\n'
        '-----BEGIN RSA PRIVATE KEY-----\nsynthetic-private-key-material\n-----END RSA PRIVATE KEY-----\n'
        'url=https://synthetic-user:synthetic-password@upstream.test/v1?token=synthetic-query-token&request_id=request-visible\n'
        'url=https://upstream.test/v1?api_key=synthetic-query-key&status=429\n'
        'url=https://upstream.test/v1?X-Amz-Signature=synthetic-signature&region=eu\n'
        'url=https://upstream.test/v1?authorization=synthetic-url-authorization&status=401\n'
        'url=https://upstream.test/status?request_id=request-visible&status=429\n'
        'path=/srv/provider/request-bodies/failure.json status=502 body=quota exhausted: try later\n'
    )
    store = IncidentStore(tmp_path / "history.json")
    store.record("redaction", "synthetic", details=details)
    report = store.get(0).format_report()
    for sensitive in (
        "synthetic-header-value", "synthetic-proxy-value", "synthetic-cookie-value",
        "synthetic-cookie-two", "synthetic-response-cookie", "synthetic-json-value",
        "synthetic-dict-cookie", "synthetic-body-key", "synthetic-private-key-material",
        "synthetic-user", "synthetic-password", "synthetic-query-token",
        "synthetic-query-key", "synthetic-signature", "synthetic-url-authorization",
    ):
        assert sensitive not in report
    for diagnostic in (
        '"status": 403', "request-visible", "explanation preserved", "&status=429", "&region=eu", "&status=401",
        "https://upstream.test/status?request_id=request-visible&status=429",
        "/srv/provider/request-bodies/failure.json", "status=502", "quota exhausted: try later",
    ):
        assert diagnostic in report


def test_history_lock_and_replacements_stay_private(tmp_path):
    path = tmp_path / "history.json"
    store = IncidentStore(path)
    old_umask = os.umask(0)
    try:
        store.record("synthetic", "first")
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        path.chmod(0o644)
        store.record("synthetic", "second")
    finally:
        os.umask(old_umask)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.with_name(path.name + ".lock").stat().st_mode) == 0o600
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.parametrize("body", [b"", b"not-json", b"null", b"{}", b"\xff", b'{"version":1,"incidents":[{}]}'])
def test_malformed_history_is_preserved_and_reported(tmp_path, body, capsys):
    path = tmp_path / "history.json"
    path.write_bytes(body)
    store = configure_incident_store(path)
    with pytest.raises(IncidentStorageError, match="malformed"):
        store.get(0)
    with pytest.raises(IncidentStorageError, match="malformed"):
        store.record("synthetic", "new error")
    assert capture_incident("synthetic", "caught error") is None
    assert "malformed" in store.last_error
    assert path.read_bytes() == body
    assert capsys.readouterr() == ("", "")


def test_atomic_replace_failure_preserves_previous_history(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    store = configure_incident_store(path)
    store.record("synthetic", "original")
    original = path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("synthetic-sensitive-failure-payload")

    monkeypatch.setattr(reporting.os, "replace", fail_replace)
    assert capture_incident("synthetic", "new") is None
    assert path.read_bytes() == original
    assert "OSError" in store.last_error
    assert "synthetic-sensitive-failure-payload" not in store.last_error
    assert list(tmp_path.glob(".*.tmp")) == []


def test_uncertain_directory_fsync_keeps_exception_id_for_retry(tmp_path, monkeypatch):
    store = configure_incident_store(tmp_path / "history.json")
    exception = RuntimeError("synthetic exception")
    real_fsync = reporting.os.fsync

    def fail_directory_fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("synthetic directory sync failure")
        real_fsync(fd)

    monkeypatch.setattr(reporting.os, "fsync", fail_directory_fsync)
    assert capture_incident("synthetic", "first", exception=exception) is None
    persisted = store.get(0).incident_id
    assert persisted == exception.incident_id
    monkeypatch.setattr(reporting.os, "fsync", real_fsync)
    assert capture_incident("synthetic", "retry", exception=exception) == persisted
    assert store.get(1) is None


@pytest.mark.parametrize("target", ["history", "lock"])
def test_symlink_targets_are_not_followed(tmp_path, target):
    path = tmp_path / "history.json"
    other = tmp_path / "other-synthetic.txt"
    other.write_text("untouched")
    link = path if target == "history" else path.with_name(path.name + ".lock")
    link.symlink_to(other)
    store = IncidentStore(path)
    with pytest.raises(IncidentStorageError):
        store.record("synthetic", "must not follow")
    assert other.read_text() == "untouched"
    assert link.is_symlink()


def test_context_scopes_are_nested_and_async_task_local(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")

    async def record(channel):
        with incident_context(channel=channel, guild="dm"):
            await asyncio.sleep(0)
            capture_incident("async", channel, context={"message": channel + "-message"})

    async def run():
        with incident_context(user="synthetic-user"):
            await asyncio.gather(record("one"), record("two"))
        capture_incident("outside", "outside")

    asyncio.run(run())
    assert store.get(0).context == {}
    for index in (1, 2):
        incident = store.get(index)
        assert incident.context == {
            "user": "synthetic-user", "channel": incident.summary, "guild": "dm",
            "message": incident.summary + "-message",
        }


def test_logging_global_capture_deduplicates_provider_and_outer_logger(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    logger = logging.Logger("synthetic.outer", logging.DEBUG)
    logger.parent = root
    logger.addHandler(handler)
    try:
        logger.warning("not captured")
        with incident_context(source="foreground", channel="channel-one"):
            try:
                raise RuntimeError("full upstream explanation")
            except RuntimeError as exception:
                first = capture_incident("provider", "caught provider", exception=exception, details="full body\n" * 10000 + "BODY-END")
                logger.exception("outer logger failure")
        logger.error("distinct no-exception error")
        logger.error("distinct no-exception error")
    finally:
        root.removeHandler(handler)
        logger.removeHandler(handler)
        handler.close()
    assert store.get(2).incident_id == first
    assert store.get(3) is None
    report = store.get(2).format_report()
    assert "ERROR synthetic.outer outer logger failure" in report
    assert "RuntimeError: full upstream explanation" in report
    assert "BODY-END" in report
    assert "Source: foreground" in report
    assert store.get(0).incident_id != store.get(1).incident_id
    assert handler.last_error is None


def test_logging_redaction_does_not_mutate_existing_log_record(tmp_path):
    secret = "synthetic-logging-credential"
    store = configure_incident_store(tmp_path / "history.json", secrets=[secret])
    handler = IncidentLoggingHandler()
    try:
        raise ValueError(secret)
    except ValueError as exception:
        record = logging.LogRecord("synthetic", logging.ERROR, __file__, 1, "failure %s", (secret,), (type(exception), exception, exception.__traceback__))
    handler.handle(record)
    assert record.getMessage() == f"failure {secret}"
    assert record.exc_text is None
    assert secret not in store.get(0).format_report()
    assert secret not in store.path.read_text()


def test_active_exception_error_without_exc_info_deduplicates_and_preserves_output(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    stream = io.StringIO()
    logger = logging.Logger("synthetic.active-exception", logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler(stream))
    try:
        raise RuntimeError("full active upstream failure")
    except RuntimeError as exception:
        first = capture_incident("provider", "caught failure", exception=exception, details="full provider body")
        logger.error(f"provider /models failed: {exception}")
    assert store.get(0).incident_id == first
    assert store.get(1) is None
    report = store.get(0).format_report()
    assert "RuntimeError: full active upstream failure" in report
    assert "test_active_exception_error_without_exc_info_deduplicates_and_preserves_output" in report
    assert "full provider body" in report
    assert stream.getvalue() == "provider /models failed: full active upstream failure\n"


def test_warnings_require_exc_info_or_an_active_exception(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    assert handler.level == logging.WARNING
    logger = logging.Logger("synthetic.warning", logging.DEBUG)
    logger.addHandler(handler)
    logger.warning("ordinary warning")
    logger.warning("empty exception tuple", exc_info=(None, None, None))
    logger.warning("only detached attribute", extra={"incident_exception": ValueError("detached")})
    assert store.get(0) is None
    try:
        raise ValueError("active warning cause")
    except ValueError as exception:
        saved_exception = exception
        logger.info("ignored info", exc_info=True)
        logger.warning("active warning without exc_info")
    assert store.get(0).summary == "active warning without exc_info"
    assert "ValueError: active warning cause" in store.get(0).traceback
    logger.warning("detached exc_info warning", exc_info=(type(saved_exception), saved_exception, saved_exception.__traceback__))
    assert store.get(1) is None
    assert "detached exc_info warning" in store.get(0).details
    logger.error("error without exception")
    logger.critical("critical without exception")
    assert store.get(0).summary == "critical without exception"
    assert store.get(1).summary == "error without exception"
    assert store.get(0).traceback == store.get(1).traceback == ""
    assert store.get(3) is None


def test_normal_cancellation_is_not_an_incident_and_still_propagates(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    logger = logging.Logger("synthetic.cancel", logging.DEBUG)
    logger.addHandler(IncidentLoggingHandler())

    async def interrupted():
        try:
            raise asyncio.CancelledError("synthetic user interrupt")
        except asyncio.CancelledError as exception:
            logger.warning("memory write cancelled")
            logger.warning("cancelled with exc_info", exc_info=True)
            logger.error("cancelled error log", extra={"incident_exception": exception})
            assert capture_incident("boundary", "cancelled", exception=exception) is None
            raise

    with pytest.raises(asyncio.CancelledError, match="synthetic user interrupt"):
        asyncio.run(interrupted())
    assert store.get(0) is None
    assert store.last_error is None


@pytest.mark.parametrize("explicit_cause", [False, True])
def test_cleanup_failure_keeps_full_cancellation_chain(tmp_path, explicit_cause):
    store = configure_incident_store(tmp_path / "history.json")
    logger = logging.Logger("synthetic.cleanup", logging.WARNING)
    logger.addHandler(IncidentLoggingHandler())
    try:
        try:
            raise asyncio.CancelledError("synthetic cancellation context")
        except asyncio.CancelledError as cancellation:
            if explicit_cause:
                raise RuntimeError("synthetic cleanup failure") from cancellation
            raise RuntimeError("synthetic cleanup failure")
    except RuntimeError as exception:
        first = capture_incident("cleanup", "cleanup actually failed", exception=exception)
        logger.warning("cleanup failed without exc_info")
    incident = store.get(0)
    assert first == incident.incident_id
    assert "CancelledError: synthetic cancellation context" in incident.traceback
    assert "RuntimeError: synthetic cleanup failure" in incident.traceback
    assert "test_cleanup_failure_keeps_full_cancellation_chain" in incident.traceback
    assert store.get(1) is None


def test_prior_true_failure_can_be_captured_while_cancellation_is_active(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    try:
        raise asyncio.CancelledError("stop requested")
    except asyncio.CancelledError:
        incident_id = capture_incident("provider", "prior 503 response", details="status=503 full prior response body")
    incident = store.get(0)
    assert incident.incident_id == incident_id
    assert incident.details == "status=503 full prior response body"
    assert incident.traceback == ""


def test_cleanup_exception_group_with_cancellation_is_not_suppressed(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    exception = BaseExceptionGroup("cleanup group", [asyncio.CancelledError("cancelled"), RuntimeError("cleanup failed")])
    assert capture_incident("cleanup", "group failure", exception=exception)
    report = store.get(0).format_report()
    assert "CancelledError: cancelled" in report and "RuntimeError: cleanup failed" in report


def test_explicit_incident_exception_captures_without_mutating_record(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    try:
        raise ValueError("detached full exception")
    except ValueError as exception:
        saved_exception = exception
    record = logging.LogRecord("synthetic", logging.ERROR, __file__, 1, "message %s", ("unchanged",), None)
    record.incident_exception = saved_exception
    formatter = logging.Formatter("%(levelname)s %(message)s")
    before_text = formatter.format(record)
    before_record = dict(record.__dict__)
    handler.handle(record)
    assert record.__dict__ == before_record
    assert record.exc_info is None
    assert record.exc_text is None
    assert formatter.format(record) == before_text == "ERROR message unchanged"
    assert "ValueError: detached full exception" in store.get(0).traceback
    assert "test_explicit_incident_exception_captures_without_mutating_record" in store.get(0).traceback


def test_exception_selection_prefers_exc_info_then_explicit_then_active(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    primary = ValueError("exc-info wins")
    attached = ValueError("explicit attribute wins")
    try:
        raise RuntimeError("active fallback")
    except RuntimeError:
        record = logging.LogRecord("synthetic", logging.ERROR, __file__, 1, "primary", (), (type(primary), primary, None))
        record.incident_exception = attached
        handler.handle(record)
        record = logging.LogRecord("synthetic", logging.ERROR, __file__, 1, "attached", (), None)
        record.incident_exception = attached
        handler.handle(record)
        record = logging.LogRecord("synthetic", logging.ERROR, __file__, 1, "active", (), None)
        record.incident_exception = "not an exception"
        handler.handle(record)
    assert store.get(2).traceback == "ValueError: exc-info wins\n"
    assert store.get(1).traceback == "ValueError: explicit attribute wins\n"
    assert "RuntimeError: active fallback" in store.get(0).traceback
    assert store.get(3) is None


def test_explicit_incident_id_skips_duplicate_log_but_preserves_output(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    first = capture_incident("tool", "non-exception failure", details="full tool body")
    snapshot = store.get(0)
    handler = IncidentLoggingHandler()
    stream = io.StringIO()
    logger = logging.Logger("synthetic.tool", logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler(stream))
    logger.error("existing tool console diagnostic", extra={"incident_id": first})
    assert store.get(0) == snapshot
    assert store.get(1) is None
    assert store.get(0).traceback == ""
    assert stream.getvalue() == "existing tool console diagnostic\n"
    logger.error("not already captured", extra={"incident_id": None})
    assert store.get(0).summary == "not already captured"
    assert store.get(1).incident_id == first


def test_logging_formatter_recursion_is_not_recaptured(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    logger = logging.Logger("synthetic.recursion", logging.ERROR)
    logger.addHandler(handler)

    class RecursiveFormatter(logging.Formatter):
        def format(self, record):
            logger.error("nested formatter error")
            return super().format(record)

    handler.setFormatter(RecursiveFormatter())
    logger.error("outer error")
    assert store.get(0).summary == "outer error"
    assert store.get(1) is None


def test_direct_store_exception_formatting_does_not_reenter_logging(tmp_path):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    logger = logging.Logger("synthetic.exception-formatting", logging.ERROR)
    logger.addHandler(handler)

    class NoisyException(RuntimeError):
        def __str__(self):
            logger.error("nested exception formatting")
            return "actual exception"

    store.record("direct", "direct capture", exception=NoisyException())
    assert store.get(0).summary == "direct capture"
    assert "actual exception" in store.get(0).traceback
    assert store.get(1) is None


def test_capture_and_logging_failures_are_nonrecursive_and_silent(tmp_path, monkeypatch, capsys):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()
    logger = logging.Logger("synthetic.storage-failure", logging.ERROR)
    logger.addHandler(handler)
    attempts = []

    def fail_record(*args, **kwargs):
        attempts.append(args)
        logger.error("nested storage failure")
        raise RuntimeError("synthetic-sensitive-storage-payload")

    def forbidden_handle_error(*args):
        pytest.fail("logging.handleError must not print the failed record")

    monkeypatch.setattr(store, "record", fail_record)
    monkeypatch.setattr(handler, "handleError", forbidden_handle_error)
    logger.error("outer error")
    assert len(attempts) == 1
    assert "RuntimeError" in handler.last_error
    assert "synthetic-sensitive-storage-payload" not in handler.last_error
    assert capture_incident("boundary", "caught failure") is None
    assert len(attempts) == 2
    assert "synthetic-sensitive-storage-payload" not in store.last_error
    assert capsys.readouterr() == ("", "")


def test_failing_formatter_does_not_break_other_logging(tmp_path, capsys):
    store = configure_incident_store(tmp_path / "history.json")
    handler = IncidentLoggingHandler()

    class BrokenFormatter(logging.Formatter):
        def format(self, record):
            raise ValueError("synthetic-sensitive-formatter-payload")

    handler.setFormatter(BrokenFormatter())
    record = logging.LogRecord("synthetic", logging.ERROR, __file__, 1, "error", (), None)
    handler.handle(record)
    assert "ValueError" in handler.last_error
    assert "synthetic-sensitive-formatter-payload" not in handler.last_error
    assert store.get(0) is None
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.handle(record)
    assert handler.last_error is None
    assert store.get(0).summary == "error"
    assert capsys.readouterr() == ("", "")
