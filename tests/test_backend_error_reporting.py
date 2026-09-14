import asyncio
import base64
import json
import logging
import sqlite3
import stat
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

import error_reporting as reporting
import site_server
from api import api_server as api
from api import auth


@pytest.fixture(autouse=True)
def isolated_reporting(monkeypatch):
    monkeypatch.setattr(reporting, "_store", None)
    monkeypatch.setattr(reporting, "_secrets", ())
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [
        handler for handler in root.handlers
        if not isinstance(handler, reporting.IncidentLoggingHandler)
    ])
    monkeypatch.setenv("MAXWELL_CONTAINER_MODE", "false")
    monkeypatch.setattr(api, "_API_GLOBAL_LIMITER", None)
    monkeypatch.setattr(api, "_API_CONCURRENCY_SEM", asyncio.Semaphore(8))
    monkeypatch.setattr(site_server, "_LIFECYCLE_LOCK", asyncio.Lock())
    monkeypatch.setattr(auth, "_auth_failures", defaultdict(list))


@pytest.fixture
def store(tmp_path):
    return reporting.configure_incident_store(tmp_path / "error_history.json")


@pytest.mark.parametrize("packages", [False, True])
def test_build_retains_complete_output_and_model_error(store, tmp_path, monkeypatch, packages):
    stdout = "BUILD-STDOUT-BEGIN\n" + "build step\n" * 1000 + "BUILD-STDOUT-END"
    stderr = "BUILD-STDERR-BEGIN\n" + "compiler detail\n" * 1000 + "BUILD-STDERR-END"
    if packages:
        monkeypatch.setattr(site_server, "_ensure_image", AsyncMock())
        docker = AsyncMock(return_value=(17, stdout, stderr))
        operation = site_server.build_site_image(tmp_path, "demo", ["redis==5.0.1"])
        expected = "could not install those packages:\n" + stderr.strip()[-600:]
    else:
        docker = AsyncMock(side_effect=[(1, "", "No such image"), (17, stdout, stderr)])
        operation = site_server._ensure_image()
        expected = "could not build the site runtime image: " + stderr.strip()[:300]
    monkeypatch.setattr(site_server, "_docker", docker)
    with reporting.incident_context(slug="demo"):
        with pytest.raises(site_server.SiteServerExecutionError) as raised:
            asyncio.run(operation)
    failure = raised.value
    assert str(failure) == expected
    assert stdout in failure.incident_details and stderr in failure.incident_details
    incident = store.get(0)
    assert incident.incident_id == failure.incident_id
    assert incident.context == {"operation": "build", "slug": "demo"}
    assert stdout in incident.details and stderr in incident.details
    assert "exitcode=17" in incident.details
    assert "Capture stack:" in incident.details and "site_server.py" in incident.details
    propagated_id = reporting.capture_incident("tool.site_server", str(failure), exception=failure)
    assert propagated_id == failure.incident_id
    assert "SiteServerExecutionError" in store.get(0).traceback
    assert store.get(1) is None
    assert docker.await_count == (1 if packages else 2)


@pytest.mark.parametrize("retry_code", [0, 23])
def test_remove_retains_all_received_attempts_without_extra_actions(store, monkeypatch, retry_code):
    first_out = "first stdout\n" * 1000
    first_err = "FIRST-ERROR-BEGIN\n" + "remove detail\n" * 1000
    retry_out = "retry stdout\n" * 1000
    retry_err = "RETRY-ERROR-BEGIN\n" + "retry detail\n" * 1000 + "RETRY-ERROR-END"
    results = [(1, first_out, first_err)] + [(0, "still-present", "inspect detail")] * 100
    results.append((retry_code, retry_out, retry_err))
    if retry_code == 0:
        results.extend([(0, "still-present", "inspect detail")] * 25)
    docker = AsyncMock(side_effect=results)
    monkeypatch.setattr(site_server, "_docker", docker)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    with pytest.raises(site_server.SiteServerExecutionError) as raised:
        asyncio.run(site_server._remove_container("demo"))
    assert str(raised.value) == (
        "could not remove backend container maxwell-site-demo: " + retry_err.strip()[:300]
    )
    incident = store.get(0)
    assert all(text in incident.details for text in (first_out, first_err, retry_out, retry_err))
    assert f"retry remove exitcode={retry_code}" in incident.details
    assert incident.details.count("inspect exitcode=0") == (125 if retry_code == 0 else 100)
    assert incident.context == {"operation": "remove", "slug": "demo"}
    assert docker.await_count == (127 if retry_code == 0 else 102)
    assert store.get(1) is None


@pytest.mark.parametrize("removed_code", [0, 1])
def test_expected_container_absence_is_not_an_incident(store, monkeypatch, removed_code):
    docker = AsyncMock(side_effect=[
        (removed_code, "", "No such container" if removed_code else ""),
        (1, "", "No such container"),
    ])
    monkeypatch.setattr(site_server, "_docker", docker)
    asyncio.run(site_server._remove_container("demo"))
    assert docker.await_count == 2
    assert not store.path.exists()


def test_absent_base_image_then_successful_build_is_not_an_incident(store, monkeypatch):
    docker = AsyncMock(side_effect=[(1, "", "No such image"), (0, "built", "")])
    monkeypatch.setattr(site_server, "_docker", docker)
    asyncio.run(site_server._ensure_image())
    assert docker.await_count == 2
    assert not store.path.exists()


@pytest.mark.parametrize("resource_type", ["image", "container"])
def test_owned_resource_expected_absence_is_not_an_incident(store, monkeypatch, resource_type):
    docker = AsyncMock(return_value=(1, "", f"No such {resource_type}"))
    monkeypatch.setattr(site_server, "_docker_raw", docker)
    assert asyncio.run(site_server.owned_resource("synthetic-resource", "site", "demo", resource_type)) is False
    docker.assert_awaited_once()
    assert not store.path.exists()


def test_ownership_inspection_failure_keeps_received_diagnostics(store, monkeypatch):
    stdout = "inspection stdout\n" * 1000
    stderr = "daemon inspection failure\n" * 1000
    monkeypatch.setattr(site_server, "_docker_raw", AsyncMock(return_value=(19, stdout, stderr)))
    with pytest.raises(site_server.SiteServerExecutionError) as raised:
        asyncio.run(site_server.owned_resource("synthetic-resource", "site", "demo", "container"))
    assert str(raised.value) == "could not verify Docker resource ownership"
    incident = store.get(0)
    assert stdout in incident.details and stderr in incident.details
    assert "exitcode=19" in incident.details
    assert incident.context == {"operation": "ownership", "slug": "demo"}


def test_validation_and_missing_app_are_not_execution_failures(store, tmp_path, monkeypatch):
    docker = AsyncMock()
    monkeypatch.setattr(site_server, "_docker", docker)
    for operation in (
        lambda: site_server.parse_files({"../app.py": "bad"}),
        lambda: site_server.parse_env({"PATH": "bad"}),
        lambda: site_server.parse_packages(["--extra-index-url"]),
        lambda: asyncio.run(site_server.start(tmp_path, "bad/slug")),
        lambda: asyncio.run(site_server.start(tmp_path, "demo")),
    ):
        with pytest.raises(site_server.SiteServerError) as raised:
            operation()
        assert not isinstance(raised.value, site_server.SiteServerExecutionError)
    docker.assert_not_awaited()
    assert not store.path.exists()


def test_reconcile_keeps_expected_warning_without_incident(store, tmp_path, monkeypatch, caplog):
    logging.getLogger().addHandler(reporting.IncidentLoggingHandler())
    monkeypatch.setattr(site_server, "_read_registry", lambda data_dir: {"demo": {"running": True}})
    monkeypatch.setattr(site_server, "_docker", AsyncMock(return_value=(0, "false", "")))
    with caplog.at_level(logging.WARNING):
        asyncio.run(site_server.reconcile(tmp_path))
    assert "Site backend demo would not restart: no app.py" in caplog.text
    assert not store.path.exists()


@pytest.fixture
def prepared_start(tmp_path, monkeypatch):
    source = tmp_path / "site_servers" / "demo"
    source.mkdir(parents=True)
    (source / "app.py").write_text("synthetic source", encoding="utf-8")
    monkeypatch.setattr(site_server, "_ensure_image", AsyncMock())
    monkeypatch.setattr(site_server, "build_site_image", AsyncMock(return_value="synthetic-image"))
    monkeypatch.setattr(site_server, "_remove_container", AsyncMock())
    monkeypatch.setattr(site_server, "get_entry", lambda *args: {"port": 8800, "running": True})
    monkeypatch.setattr(site_server, "_write_entry", Mock())
    monkeypatch.setattr(site_server, "_http_ping", AsyncMock(return_value="no HTTP response"))
    monkeypatch.setattr(site_server, "_port_is_free", lambda port: True)
    return tmp_path


def test_start_failure_retains_full_output_and_original_result(store, prepared_start, monkeypatch):
    stdout = "RUN-STDOUT-BEGIN\n" + "run detail\n" * 1000 + "RUN-STDOUT-END"
    stderr = "knownfakekey START-STDERR-BEGIN\n" + "run failure\n" * 1000 + "START-STDERR-END"
    docker = AsyncMock(return_value=(125, stdout, stderr))
    monkeypatch.setattr(site_server, "_docker", docker)
    with pytest.raises(site_server.SiteServerExecutionError) as raised:
        asyncio.run(site_server.start(prepared_start, "demo", env={"API_KEY": "knownfakekey"}))
    assert str(raised.value) == "could not start the backend: " + stderr.strip()[:300]
    entry = site_server._write_entry.call_args.args[2]
    assert entry["health"] == "start failed: " + stderr.strip()[:300]
    assert entry["running"] is False
    incident = store.get(0)
    assert stdout in incident.details
    assert stderr.replace("knownfakekey", "[REDACTED]") in incident.details
    assert "knownfakekey" not in store.path.read_text(encoding="utf-8")
    assert "exitcode=125" in incident.details
    assert incident.context == {"operation": "start", "slug": "demo"}
    assert docker.await_count == 1
    assert store.get(1) is None


@pytest.mark.parametrize("credential_name", ["API_KEY", "CUSTOM_API_KEY", "CUSTOM_TOKEN", "CUSTOM_PASSWORD", "CUSTOM_SECRET", "X_CT0"])
def test_successful_start_does_not_redact_ordinary_env_values(store, prepared_start, monkeypatch, credential_name):
    env = {"DEBUG": "1", "MODE": "dev", credential_name: "syntheticsecret"}
    original_env = dict(env)
    docker = AsyncMock(return_value=(0, "synthetic-container-id", ""))
    monkeypatch.setattr(site_server, "_docker", docker)
    monkeypatch.setattr(site_server, "_wait_healthy", AsyncMock(return_value="ok"))
    entry = asyncio.run(site_server.start(prepared_start, "demo", env=env))
    assert entry["running"] is True
    assert entry["env"] == original_env == env
    assert site_server._write_entry.call_args.args[2]["env"] == original_env
    assert all(f"{name}={value}" in docker.await_args.args for name, value in original_env.items())
    assert not store.path.exists()
    summary = "status=501 line=11 path=/dev/site1"
    context = {"path": "/dev/site1", "line": "11", "status": "501"}
    reporting.capture_incident(
        "unrelated.dev1", summary, details="dev1 credential was syntheticsecret", context=context,
    )
    incident = store.get(0)
    assert incident.source == "unrelated.dev1"
    assert incident.summary == summary
    assert incident.context == context
    assert incident.details == "dev1 credential was [REDACTED]"
    assert "syntheticsecret" not in store.path.read_text(encoding="utf-8")


def test_unhealthy_start_keeps_full_received_logs_but_model_tail_unchanged(store, prepared_start, monkeypatch):
    stdout = "EARLY-APP-OUTPUT\n" + "app output\n" * 1000
    stderr = "APP-TRACEBACK-BEGIN\n" + "app traceback\n" * 1000 + "APP-TRACEBACK-END"
    docker = AsyncMock(side_effect=[(0, "container-id", "run warning"), (0, stdout, stderr), (0, stdout, stderr)])
    monkeypatch.setattr(site_server, "_docker", docker)
    monkeypatch.setattr(site_server, "_wait_healthy", AsyncMock(return_value="it keeps crashing on startup (exit code 1)"))
    with pytest.raises(site_server.SiteServerExecutionError) as raised:
        asyncio.run(site_server.start(prepared_start, "demo"))
    tail = (stdout + stderr).strip()[-4000:]
    assert str(raised.value).endswith("Its last output:\n" + tail)
    assert "EARLY-APP-OUTPUT" not in str(raised.value)
    incident = store.get(0)
    assert stdout in incident.details and stderr in incident.details
    assert "container-id" in incident.details and "run warning" in incident.details
    assert site_server._remove_container.await_count == 2
    assert docker.await_args_list[1].args == ("logs", "--tail", "30", "maxwell-site-demo")
    assert asyncio.run(site_server.logs(prepared_start, "demo")) == tail
    assert docker.await_count == 3
    assert store.get(1) is None


def test_start_retains_failed_health_inspect_output(store, prepared_start, monkeypatch):
    stdout = "HEALTH-STDOUT-BEGIN\n" + "inspect output\n" * 1000
    stderr = "HEALTH-STDERR-BEGIN\n" + "inspect failure\n" * 1000 + "HEALTH-STDERR-END"
    docker = AsyncMock(side_effect=[(0, "container-id", ""), (1, stdout, stderr), (0, "app log", "")])
    monkeypatch.setattr(site_server, "_docker", docker)
    with pytest.raises(site_server.SiteServerExecutionError, match="the container disappeared"):
        asyncio.run(site_server.start(prepared_start, "demo"))
    incident = store.get(0)
    assert stdout in incident.details and stderr in incident.details
    assert "health inspect exitcode=1" in incident.details
    assert docker.await_count == 3
    assert site_server._START_DIAGNOSTICS.get() is None
    assert store.get(1) is None


@pytest.mark.parametrize("cancelled", [False, True])
def test_docker_timeout_keeps_cause_without_draining_and_cancellation_is_ignored(store, monkeypatch, cancelled):
    cause = asyncio.CancelledError("intentional cancellation") if cancelled else TimeoutError("transport diagnostic")
    proc = SimpleNamespace(
        communicate=AsyncMock(side_effect=cause), kill=Mock(),
        wait=AsyncMock(return_value=-9), returncode=-9,
    )
    spawn = AsyncMock(return_value=proc)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    expected = asyncio.CancelledError if cancelled else site_server.SiteServerExecutionError
    with pytest.raises(expected) as raised:
        asyncio.run(site_server._docker_raw("inspect", "synthetic-container", timeout=2))
    spawn.assert_awaited_once()
    proc.communicate.assert_awaited_once()
    proc.kill.assert_called_once()
    proc.wait.assert_awaited_once()
    if cancelled:
        assert raised.value is cause
        assert not store.path.exists()
    else:
        assert str(raised.value) == "docker did not respond within 2s"
        assert raised.value.__cause__ is cause
        incident = store.get(0)
        assert "transport diagnostic" in incident.traceback
        assert "unread output was not recovered" in incident.details
        assert "exitcode=-9" in incident.details
        assert incident.incident_id == cause.incident_id == raised.value.incident_id


def test_missing_docker_keeps_original_exception_chain(store, monkeypatch):
    cause = FileNotFoundError("synthetic docker executable is missing")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(side_effect=cause))
    with pytest.raises(site_server.SiteServerExecutionError) as raised:
        asyncio.run(site_server._docker_raw("image", "inspect", "synthetic-image"))
    assert str(raised.value) == "docker is not installed or not on PATH"
    assert raised.value.__cause__ is cause
    assert "synthetic docker executable is missing" in store.get(0).traceback


@pytest.fixture
def api_reporting(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    monkeypatch.setenv("SYNTHETIC_API_KEY", "knownfakekey")
    asyncio.run(api._initialize_incident_reporting(web.Application()))
    return reporting.get_incident_store()


def test_api_startup_configures_shared_private_path_without_writes(tmp_path, monkeypatch):
    path = tmp_path / "private-data" / "error_history.json"
    monkeypatch.setattr(api, "DATA_DIR", path.parent)
    assert api._initialize_incident_reporting in api.app.on_startup
    asyncio.run(api._initialize_incident_reporting(web.Application()))
    first_store = reporting.get_incident_store()
    asyncio.run(api._initialize_incident_reporting(web.Application()))
    assert reporting.get_incident_store().path == first_store.path == path
    assert not path.parent.exists()
    handlers = [handler for handler in logging.getLogger().handlers if isinstance(handler, reporting.IncidentLoggingHandler)]
    assert len(handlers) == 1 and handlers[0].level == logging.WARNING
    bot_store = reporting.IncidentStore(path)
    bot_store.record("bot", "synthetic bot incident")
    logging.getLogger("synthetic.api").error("synthetic API incident")
    assert bot_store.get(0).summary == "synthetic API incident"
    assert bot_store.get(1).summary == "synthetic bot incident"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.with_name(path.name + ".lock").stat().st_mode) == 0o600


@pytest.mark.parametrize("name", ["CUSTOM_API_KEY", "CUSTOM_TOKEN", "CUSTOM_PASSWORD", "CUSTOM_SECRET", "X_CT0", "API_KEY"])
def test_api_startup_registers_configured_credentials(tmp_path, monkeypatch, name):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    monkeypatch.setenv(name, "  knownfakekey  ")
    asyncio.run(api._initialize_incident_reporting(web.Application()))
    reporting.capture_incident("synthetic", "failure includes knownfakekey")
    store = reporting.get_incident_store()
    assert store.get(0).summary == "failure includes [REDACTED]"
    assert "knownfakekey" not in store.path.read_text(encoding="utf-8")


def test_caught_api_500_preserves_response_traceback_and_full_redacted_diagnostics(api_reporting, monkeypatch):
    diagnostic = "knownfakekey SQL-ERROR-BEGIN\n" + "database explanation\n" * 1500 + "SQL-ERROR-END"
    cause = sqlite3.OperationalError(diagnostic)
    monkeypatch.setattr(api, "_has_admin_auth", lambda request: True)
    monkeypatch.setattr(api, "_rag_query", Mock(side_effect=cause))
    request = make_mocked_request("GET", "/api/rag/ltm?private-query=not-recorded", headers={
        "Authorization": "Bearer not-recorded-authorization",
        "Cookie": "not-recorded-cookie",
    })
    response = asyncio.run(api._reliability_middleware(request, api.rag_ltm_list))
    assert response.status == 500
    assert response.text == json.dumps({"error": "rag db: " + diagnostic})
    assert response.headers["Access-Control-Allow-Origin"] == auth.CORS_ORIGIN
    incident = api_reporting.get(0)
    assert incident.incident_id == cause.incident_id
    assert response.text.replace("knownfakekey", "[REDACTED]") in incident.details
    assert diagnostic.replace("knownfakekey", "[REDACTED]") in incident.traceback
    assert "rag_ltm_list" in incident.traceback
    assert incident.context == {"method": "GET", "path": "/api/rag/ltm", "status": "500"}
    assert "not-recorded" not in incident.format_report()
    assert "knownfakekey" not in api_reporting.path.read_text(encoding="utf-8")
    assert api_reporting.get(1) is None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 429])
def test_caught_normal_4xx_is_not_an_incident(api_reporting, status):
    async def handler(request):
        try:
            raise ValueError("ordinary invalid input")
        except ValueError as exc:
            return auth._json_response({"error": str(exc)}, status)

    request = make_mocked_request("POST", "/api/validation")
    response = asyncio.run(api._reliability_middleware(request, handler))
    assert response.status == status
    assert json.loads(response.text) == {"error": "ordinary invalid input"}
    assert not api_reporting.path.exists()


@pytest.mark.parametrize("operation", ["logs", "restart"])
def test_container_pm2_refusals_do_not_evict_incidents(api_reporting, monkeypatch, operation):
    monkeypatch.setenv("MAXWELL_CONTAINER_MODE", "true")
    monkeypatch.setenv("MAXWELL_ADMIN_USER", "synthetic-admin")
    monkeypatch.setenv("MAXWELL_ADMIN_PASSWORD", "synthetic-password")
    spawn = AsyncMock(side_effect=AssertionError("unsupported PM2 command executed"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    ids = [reporting.capture_incident("synthetic.failure", f"real incident {index}") for index in range(10)]
    original_history = api_reporting.path.read_bytes()
    credentials = base64.b64encode(b"synthetic-admin:synthetic-password").decode()
    handler = api.pm2_logs if operation == "logs" else api.pm2_restart

    async def authenticated_handler(request):
        return await auth._auth_middleware_unless_login(request, handler)

    for _ in range(10):
        request = make_mocked_request(
            "GET" if operation == "logs" else "POST", f"/api/pm2/{operation}",
            headers={"Authorization": "Basic " + credentials},
        )
        response = asyncio.run(api._reliability_middleware(request, authenticated_handler))
        assert response.status == 501
        assert response.text == json.dumps({"error": f"Use instance.sh <id> {operation} on the host"})
        assert response.headers["Access-Control-Allow-Origin"] == auth.CORS_ORIGIN
    spawn.assert_not_awaited()
    assert api_reporting.path.read_bytes() == original_history
    assert [api_reporting.get(index).incident_id for index in range(10)] == list(reversed(ids))


@pytest.mark.parametrize("status,expected_refusal", [
    (500, False), (501, False), (502, False), (504, False),
    (500, True), (502, True), (504, True),
])
def test_refusal_exclusion_keeps_genuine_api_failures(api_reporting, status, expected_refusal):
    cause = RuntimeError(f"genuine HTTP {status} failure")

    async def handler(request):
        try:
            raise cause
        except RuntimeError as exc:
            return auth._json_response({"error": str(exc)}, status, expected_refusal=expected_refusal)

    request = make_mocked_request("GET", "/api/synthetic")
    response = asyncio.run(api._reliability_middleware(request, handler))
    assert response.status == status
    assert response.text == json.dumps({"error": str(cause)})
    incident = api_reporting.get(0)
    assert incident.incident_id == cause.incident_id
    assert str(cause) in incident.traceback
    assert incident.details == response.text
    assert incident.context == {"method": "GET", "path": "/api/synthetic", "status": str(status)}
    assert api_reporting.get(1) is None


@pytest.mark.parametrize("timeout", [False, True])
def test_outer_api_failures_keep_request_context_and_deduplicate_logs(api_reporting, timeout):
    cause = TimeoutError("synthetic timed out") if timeout else RuntimeError("synthetic unhandled failure")

    async def handler(request):
        raise cause

    request = make_mocked_request("PUT", "/api/synthetic")
    response = asyncio.run(api._reliability_middleware(request, handler))
    assert response.status == (504 if timeout else 500)
    assert json.loads(response.text) == {"error": "request timed out" if timeout else "internal error"}
    incident = api_reporting.get(0)
    assert incident.context == {"method": "PUT", "path": "/api/synthetic"}
    assert str(cause) in incident.traceback
    assert incident.incident_id == cause.incident_id
    assert api_reporting.get(1) is None
    reporting.capture_incident("outside", "after request")
    assert api_reporting.get(0).context == {}


def test_api_intentional_cancellation_is_not_an_incident(api_reporting):
    async def handler(request):
        raise asyncio.CancelledError("intentional cancellation")

    request = make_mocked_request("GET", "/api/synthetic")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(api._reliability_middleware(request, handler))
    assert not api_reporting.path.exists()


@pytest.mark.parametrize("authenticated", [False, True])
def test_incident_history_is_never_exported_by_data_route(api_reporting, monkeypatch, authenticated):
    reporting.capture_incident("synthetic", "PRIVATE-DIAGNOSTIC-NEVER-PUBLIC")
    monkeypatch.setenv("MAXWELL_ADMIN_USER", "synthetic-admin")
    monkeypatch.setenv("MAXWELL_ADMIN_PASSWORD", "synthetic-password")
    credentials = base64.b64encode(b"synthetic-admin:synthetic-password").decode()
    headers = {"Authorization": "Basic " + credentials} if authenticated else {}
    request = make_mocked_request(
        "GET", "/data/error_history.json", headers=headers, match_info={"file": "error_history.json"},
    )

    async def authenticated_data(request):
        return await auth._auth_middleware_unless_login(request, api.data_file)

    response = asyncio.run(api._reliability_middleware(request, authenticated_data))
    assert response.status == (403 if authenticated else 401)
    assert json.loads(response.text) == {"error": "not allowed" if authenticated else "unauthorized"}
    assert "PRIVATE-DIAGNOSTIC" not in response.text
    assert api_reporting.get(1) is None


def test_site_proxy_timeout_is_private_and_response_is_unchanged(api_reporting, monkeypatch):
    cause = TimeoutError("full synthetic site transport diagnosis")
    session = SimpleNamespace(request=AsyncMock(side_effect=cause), close=AsyncMock())
    monkeypatch.setattr(api.aiohttp, "ClientSession", lambda **kwargs: session)
    monkeypatch.setattr(api, "_SITE_PROXY_RATE", SimpleNamespace(allow=lambda key: True))
    monkeypatch.setattr(api, "_site_server_enabled", lambda slug: True)
    monkeypatch.setattr(site_server, "target_for", lambda data_dir, slug: ("synthetic-site", 8000))
    request = make_mocked_request("GET", "/bot/demo/api/items", match_info={"slug": "demo", "path": "items"})
    response = asyncio.run(api._reliability_middleware(request, api.site_proxy))
    assert response.status == 504
    assert json.loads(response.text) == {"error": "the site backend timed out"}
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    incident = api_reporting.get(0)
    assert str(cause) in incident.traceback
    assert incident.context == {"method": "GET", "path": "/bot/demo/api/items", "slug": "demo"}
    session.request.assert_awaited_once()
    session.close.assert_awaited_once()
    assert api_reporting.get(1) is None


def test_generated_error_response_body_passes_through_unchanged(api_reporting, monkeypatch):
    body = b'{"error": "generated app diagnosis, not a Discord automatic notice"}'

    async def chunks(size):
        yield body

    upstream = SimpleNamespace(
        status=500, headers={"Content-Type": "application/json"},
        content=SimpleNamespace(iter_chunked=chunks), release=Mock(),
    )
    session = SimpleNamespace(request=AsyncMock(return_value=upstream), close=AsyncMock())
    response = SimpleNamespace(status=500, headers={}, prepare=AsyncMock(), write=AsyncMock(), write_eof=AsyncMock())
    monkeypatch.setattr(api.aiohttp, "ClientSession", lambda **kwargs: session)
    monkeypatch.setattr(api.web, "StreamResponse", lambda **kwargs: response)
    monkeypatch.setattr(api, "_SITE_PROXY_RATE", SimpleNamespace(allow=lambda key: True))
    monkeypatch.setattr(api, "_site_server_enabled", lambda slug: True)
    monkeypatch.setattr(site_server, "target_for", lambda data_dir, slug: ("synthetic-site", 8000))
    request = make_mocked_request("GET", "/bot/demo/api/items", match_info={"slug": "demo", "path": "items"})
    result = asyncio.run(api._reliability_middleware(request, api.site_proxy))
    assert result is response and result.status == 500
    response.write.assert_awaited_once_with(body)
    assert response.headers == {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
    upstream.release.assert_called_once()
    session.request.assert_awaited_once()
    session.close.assert_awaited_once()
