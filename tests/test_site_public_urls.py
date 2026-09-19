import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

import bot_tools
import site_server
import site_test
from bot_tools import (
    CreateSiteTool,
    EditSiteTool,
    HDImageGeneratorTool,
    ImageGeneratorTool,
    ListSitesTool,
    SiteServerTool,
    SiteTestTool,
)


LOCAL = "http://127.0.0.1:8081"
LOCAL_SITE = LOCAL + "/bot"
PUBLIC = "https://redroom.zombiedawn.net/dame"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PAGE = (
    "<!doctype html><html><head><title>Demo</title></head>"
    "<body><h1>before</h1><script>fetch('/bot/demo/api/notes')</script></body></html>"
)
ABOUT = "<!doctype html><html><head><title>Local about</title></head><body><h1>About</h1></body></html>"
URL_CASES = [
    pytest.param((None, LOCAL_SITE), id="unset"),
    pytest.param(("", LOCAL_SITE), id="empty"),
    pytest.param((" \t", LOCAL_SITE), id="whitespace"),
    pytest.param((PUBLIC, PUBLIC), id="explicit"),
    pytest.param((PUBLIC + "/", PUBLIC), id="trailing-slash"),
    pytest.param((" " + PUBLIC + "/// ", PUBLIC), id="surrounding-space-and-slashes"),
]


@pytest.fixture(params=URL_CASES)
def site_case(request, tmp_path, monkeypatch):
    override, expected = request.param
    monkeypatch.setenv("DAME_CURIE_CONTAINER_MODE", "false")
    root = tmp_path / "public"
    data = tmp_path / "data"
    root.mkdir()
    data.mkdir()
    image = root / "source.png"
    image.write_bytes(PNG)
    config = SimpleNamespace(
        DAME_CURIE_SITE_DIR=str(root), DAME_CURIE_PUBLIC_BASE_URL=LOCAL + "///",
        DATA_DIR=str(data), IMAGE_GEN_PROTOCOL="images", GEMINI_IMAGE_PROTOCOL="images",
        IMAGE_GEN_BASE_URL="https://images.example.invalid/v1",
        GEMINI_IMAGE_BASE_URL="https://images.example.invalid/v1",
    )
    if override is not None:
        config.DAME_CURIE_SITE_PUBLIC_BASE_URL = override
    control = {"create_site_quota_per_user": 50, "knowledge_graph_enabled": False}
    bot = SimpleNamespace(
        config=config, _sites={}, _control=control, control=control, tools={},
        _load_sites=lambda quiet=True: None, _is_admin=lambda uid: False,
        memory=SimpleNamespace(add_to_channel_memory=AsyncMock()),
        _current_progress_by_channel={},
    )
    message = SimpleNamespace(
        author=SimpleNamespace(id=42, display_name="synthetic"), attachments=[],
        channel=SimpleNamespace(id=42, send=AsyncMock(return_value=SimpleNamespace(
            attachments=[SimpleNamespace(url="https://cdn.example.invalid/image.png")],
        ))),
    )
    create = CreateSiteTool(bot)
    result = asyncio.run(create.execute(
        message, name="demo", title="Demo", body=PAGE, backend=True,
        files={"about/index.html": ABOUT},
        images=[{"path": str(image), "filename": "plot.png"}],
    ))
    return SimpleNamespace(
        bot=bot, message=message, root=root, create=create, created=result,
        expected=expected, override=override,
    )


def test_create_advertises_site_root_and_bundled_images_without_rewriting_files(site_case):
    case = site_case
    expected = case.expected + "/demo/"
    assert case.create.get_description().startswith(f"Publish a site at {case.expected}/<name>/.")
    assert case.created.startswith(f"Site created: {expected}\n")
    assert f"  - {expected}images/plot.png" in case.created
    assert "/api/site/demo" in case.created
    assert (case.root / "demo/index.html").read_text() == PAGE
    assert (case.root / "demo/about/index.html").read_text() == ABOUT
    assert (case.root / "demo/images/plot.png").read_bytes() == PNG
    assert case.bot._sites["demo"]["path"] == str(case.root / "demo")
    assert case.bot._sites["demo"]["backend"] is True
    assert case.bot.config.DAME_CURIE_PUBLIC_BASE_URL == LOCAL + "///"


def test_edit_and_list_advertise_site_root_but_keep_operational_base(site_case):
    case = site_case
    edit = EditSiteTool(case.bot)
    assert edit.base_url == LOCAL_SITE
    listing = asyncio.run(edit.execute(case.message, name="demo", action="list"))
    assert listing.startswith(case.expected + "/demo/\n")
    written = asyncio.run(edit.execute(
        case.message, name="demo", action="write", path="style.css", content="body{color:red}",
    ))
    assert written.startswith(f"Wrote style.css → {case.expected}/demo/\n")
    patched = asyncio.run(edit.execute(
        case.message, name="demo", action="replace", find="<h1>before</h1>", replace="<h1>after</h1>",
    ))
    assert patched.startswith(f"Patched index.html → {case.expected}/demo/\n")
    renamed = asyncio.run(edit.execute(case.message, name="demo", action="rename", title="Renamed"))
    assert renamed == f"Retitled demo → 'Renamed' ({case.expected}/demo/)"
    extended = asyncio.run(edit.execute(case.message, name="demo", action="extend", permanent=True))
    assert extended == f"demo: permanent ({case.expected}/demo/)"
    listed = asyncio.run(ListSitesTool(case.bot).execute(case.message))
    assert f"demo — {case.expected}/demo/ — 'Renamed'" in listed
    assert (case.root / "demo/style.css").read_text() == "body{color:red}"
    assert (case.root / "demo/index.html").read_text() == PAGE.replace("<h1>before</h1>", "<h1>after</h1>")
    assert edit.base_url == LOCAL_SITE


def test_backend_deployment_and_edit_backend_announcements_remain_local(site_case, monkeypatch):
    case = site_case
    start = AsyncMock(return_value={"port": 8000})
    monkeypatch.setattr(site_server, "start", start)
    server = SiteServerTool(case.bot)
    result = asyncio.run(server.execute(
        case.message, name="demo", action="write", files={"app.py": "print('synthetic')\n"},
    ))
    assert result.startswith(f"Backend server live: {LOCAL_SITE}/demo/api/ ")
    assert PUBLIC not in result
    assert server.base_url == LOCAL_SITE
    start.assert_awaited_once_with(case.bot.config.DATA_DIR, "demo", env=None, packages=None)
    assert site_server.read_code(case.bot.config.DATA_DIR, "demo", "app.py") == "print('synthetic')\n"
    assert case.bot._sites["demo"]["server"] is True
    edit = EditSiteTool(case.bot)
    listing = asyncio.run(edit.execute(case.message, name="demo", action="list"))
    assert listing.startswith(case.expected + "/demo/\n")
    assert f"Python backend: on at {LOCAL_SITE}/demo/api/ (app.py)." in listing
    assert f"Python backend: on at {PUBLIC}" not in listing
    backend = asyncio.run(edit.execute(case.message, name="demo", action="backend", backend=True))
    assert "/api/site/demo" in backend
    assert PUBLIC not in backend


def test_site_test_keeps_local_subpage_assets_and_backend_probe_urls(site_case, monkeypatch):
    case = site_case
    case.bot._sites["demo"]["server"] = True
    http = AsyncMock(return_value=(200, b"<title>Not the local page</title>", ""))
    browser = AsyncMock(return_value={
        "browser": "synthetic", "http_status": 200, "console_errors": [],
        "visible_text": "About this synthetic local page", "rendered_nodes": 3,
    })
    monkeypatch.setattr(site_test, "http_get", http)
    monkeypatch.setattr(site_test, "probe_browser", browser)
    monkeypatch.setattr(site_server, "logs", AsyncMock(return_value=""))
    tool = SiteTestTool(case.bot)
    report = asyncio.run(tool.execute(case.message, name="demo", path="about/", screenshot=False))
    assert tool.base_url == LOCAL_SITE
    assert report.startswith(f"SITE TEST {LOCAL_SITE}/demo/about/\nTitle: Local about\n")
    assert PUBLIC not in report
    assert http.await_args_list == [
        call(LOCAL_SITE + "/demo/about/"),
        call(LOCAL_SITE + "/demo/api/"),
        call(LOCAL + "/api/site/demo/kv"),
    ]
    browser.assert_awaited_once_with(LOCAL_SITE + "/demo/about/", wait=2.0, screenshot=False)


@pytest.mark.parametrize("tool_class", [ImageGeneratorTool, HDImageGeneratorTool], ids=["normal", "hd"])
@pytest.mark.parametrize("auto_send", [False, True], ids=["saved", "sent"])
def test_website_override_leaves_image_delivery_urls_and_bytes_unchanged(site_case, monkeypatch, tool_class, auto_send):
    case = site_case
    request = AsyncMock(return_value=(PNG, "png", ""))
    monkeypatch.setattr(bot_tools, "_native_image_request", request)
    result = asyncio.run(tool_class(case.bot).execute(case.message, prompt="synthetic image", auto_send=auto_send))
    request.assert_awaited_once()
    files = list((case.root / "_images").glob("*.png"))
    assert len(files) == 1
    assert files[0].read_bytes() == PNG
    assert files[0].with_suffix(".txt").read_bytes() == b"synthetic image"
    assert files[0].with_suffix(".txt").name not in result
    assert f"Permanent URL: {LOCAL_SITE}/_images/{files[0].name} " in result
    assert "redroom.zombiedawn.net" not in result
    assert f"Local path: {files[0]} " in result
    if auto_send:
        case.message.channel.send.assert_awaited_once()
        assert "Image URL: https://cdn.example.invalid/image.png" in result
    else:
        case.message.channel.send.assert_not_awaited()
        assert "NOT sent" in result
    assert case.bot.config.DAME_CURIE_SITE_DIR == str(case.root)
    assert case.bot.config.DAME_CURIE_PUBLIC_BASE_URL == LOCAL + "///"
