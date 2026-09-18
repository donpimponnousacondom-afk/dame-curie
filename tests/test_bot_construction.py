import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONSTRUCTION_PROBE = """
import asyncio
import errno
import json
import os
from pathlib import Path
import sys

app = Path.cwd().resolve()
state = Path(os.environ['HOME']).parent.resolve()
blocked = []


def protect(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'subprocess.Popen'}:
        blocked.append(event)
        raise AssertionError('constructor attempted network or process launch')
    paths = []
    if event == 'open' and isinstance(args[0], (str, bytes)):
        if args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            paths = [args[0]]
    elif event == 'sqlite3.connect':
        paths = [args[0]]
    elif event == 'os.mkdir':
        if not Path(args[0]).is_dir():
            paths = [args[0]]
    elif event in {'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate', 'os.utime'}:
        paths = [args[0]]
    elif event in {'os.rename', 'os.link'}:
        paths = [args[0], args[1]]
    elif event == 'os.symlink':
        paths = [args[1]]
    for value in paths:
        path = Path(os.fsdecode(value)).resolve()
        if not path.is_relative_to(state):
            blocked.append(str(path))
            raise OSError(errno.EROFS, 'constructor write outside isolated state', str(path))


sys.addaudithook(protect)
from bot import MaxwellBot


async def construct():
    instance = MaxwellBot()
    data = Path(instance.config.DATA_DIR)
    assert data == state / 'data'
    assert instance.plugin_manager.data_dir == data
    assert instance.plugin_manager.state_file == data / 'plugins.json'
    assert json.loads((data / 'plugins.json').read_text())['plugins']
    assert 'checkers' in instance.plugin_manager.loaded_plugins
    assert instance.memory.db_path == data / 'maxwell_rag.db'
    assert instance.memory.embedding_status()['total'] == 0
    assert instance.bg_jobs.data_path == str(data / 'background_jobs.json')
    assert instance._watermarks.path == str(data / 'watermarks.json')
    assert instance.rem_store.data_dir == data
    assert instance.autonomy_engine.store.data_dir == data
    assert instance.user is None
    assert instance.ai_provider._session is None
    assert not instance.ai_provider.available
    assert not instance.memory._embed_tasks
    assert not instance.plugin_manager._jobs_started
    assert instance.autonomy_engine._task is None
    assert not (app / 'data').exists()
    instance.memory._db.close()
    await instance.close()
    assert not blocked, blocked
    print('actual MaxwellBot constructor passed without login or network')


asyncio.run(construct())
"""


@pytest.mark.parametrize("external_prompts", [False, True])
def test_actual_bot_constructor_keeps_state_outside_read_only_source(
    tmp_path, external_prompts
):
    app = tmp_path / "app"
    app.mkdir()
    for line in (ROOT / "docker/app.Dockerfile.dockerignore").read_text().splitlines():
        if line.startswith("!"):
            relative = line[1:]
            target = app / relative
            if relative.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
    state = tmp_path / "state"
    for directory in ("home", "data", "sites", "prompts", "tmp"):
        (state / directory).mkdir(parents=True)
    (state / "prompts/personality.txt").write_text("Synthetic constructor personality")
    env = {
        "PATH": os.defpath,
        "PYTHONPATH": os.pathsep.join([str(app), *filter(None, sys.path)]),
        "HOME": str(state / "home"),
        "TMPDIR": str(state / "tmp"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "MAXWELL_ENV_FILE": "/dev/null",
        "MAXWELL_CONTAINER_MODE": "true",
        "DATA_DIR": str(state / "data"),
        "MAXWELL_SITE_DIR": str(state / "sites"),
        "MAXWELL_PROMPTS_DIR": str(state / "prompts") if external_prompts else "",
        "DISCORD_TOKEN": "synthetic-constructor-token-never-used",
        "MAXWELL_ADMIN_PASSWORD": "synthetic-constructor-password-never-used",
        "OLLAMA_BASE_URL": "http://127.0.0.1:9/v1",
        "OLLAMA_MODEL": "synthetic-no-network-model",
        "BOT_PERSONA_TYPE": "maxwell",
        **dict.fromkeys(
            (
                "ENABLE_RAG",
                "ENABLE_AUTONOMY",
                "ENABLE_TELEGRAM",
                "ENABLE_EMAIL_TOOLS",
                "ENABLE_X",
                "ENABLE_VC",
                "ENABLE_TTS",
                "ENABLE_IMAGE_GEN",
            ),
            "false",
        ),
        "ENABLE_SHELL": "true",
        "ENABLE_CREATE_SITE": "true",
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", textwrap.dedent(CONSTRUCTION_PROBE)],
        cwd=app,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "actual MaxwellBot constructor passed" in result.stdout
    assert not (app / "data").exists()
