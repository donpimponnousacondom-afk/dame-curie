# Development and validation

## Python and environments

Python 3.14 is mandatory. Never replace system Python, install into its package tree or use a system-package bypass. `.venv/` is an environment; `.env`, `bot.env` and `deploy.env` are configuration files and may hold secrets.

New checkout environment:

```sh
python3.14 -m venv .venv
.venv/bin/python --version
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
```

Do not use `--system-site-packages`, `--clear` or a generic `python3`. `install.sh` (also through `setup.sh`) installs host dependencies and the app requirements; it does not deploy. The image uses `docker/requirements.lock`; the shell venv inside the container uses `docker/shell-requirements.lock` (see [OPERATIONS.md](OPERATIONS.md)). `/opt/dame-curie/.venv` is the root-owned operator venv, not a development environment.

Known pin conflict: `discord-ext-voice-recv==0.5.2a179` declares `discord-py` while the lock supplies `discord.py-self==2.1.0`; `pip check` reports it. Do not install the competing distribution or weaken pins. Voice is unverified.

## Quality gate

`scripts/lint.sh [--staged]` is the gate. The commit hook (`.githooks/pre-commit`) runs it with `--staged`; CI (`.github/workflows/quality.yml`) runs it on the tree. Enable the hook once per clone: `git config core.hooksPath .githooks`.

- Dash check (`scripts/check_dashes.sh`): no em or en dash in tracked files; `audit/` is excluded.
- `ruff check`: the whole tree, or the staged `.py` files in the hook. Zero findings is the standard. Suppress one line only with `# noqa: CODE` and a reason on the same line.
- `ruff format --check`: added `.py` files only. The gate never reformats legacy files. Do not reformat code you did not change.
- The tool is `ruff==0.17.3` from `requirements-dev.txt`. The script stops with the cause when ruff is missing or has another version.
- Configuration: `[tool.ruff]` in `pyproject.toml` (line length 88, target `py314`, a curated rule set). Mypy is not run and has no configuration.

## Tests and isolated QA

New tests are allowed and wanted. Each fix gets a regression test that fails on the old code. Tests run only in an isolated container. Never import the application or collect tests on the host.

- `scripts/build_qa_image.sh <app-tag>` builds `dame-curie-qa:<app-tag>` from `docker/qa.Dockerfile`: the app image plus `docker/qa-requirements.lock` (pytest pins), `git`, `rsync` and `openssh-client`. Rebuild it when a lock file changes; otherwise tests run on stale libraries.
- `QA_IMAGE=dame-curie-qa:<app-tag> scripts/qa.sh <tree-ish> <outfile> [pytest args]` runs the suite from a Git archive of `<tree-ish>` with network none, a read-only root, no private mounts and a synthetic environment. `QA_IMAGE` is required. The script excludes `tests/test_streaming.py` and `tests/test_streaming_primary.py`. It writes the pytest output and `exit=<rc>` to `<outfile>`. `<tree-ish>` is a commit or a tree. To test the staged index before a commit, pass `$(git write-tree)`.
- Never run the historical live-provider version of `tests/test_tool_progress.py::test_streaming_tick_inserts_space_between_glued_deltas`; only its synthetic replacement is in the suite.
- Run a negative control: the new test fails on `main` and passes on the branch. Record both outputs in the PR.
- `pytest.ini` sets `pythonpath = .`, `testpaths = tests` and ignores `DeprecationWarning`.

## Dead-code audit, report only

Vulture 2.16 (`requirements-dev.txt`) parses with `ast` and does not import the application. Its findings are leads, not deletion authority: callbacks, serializers and dynamic registration give false positives, and repeated names hide dead code. There is no gate and no whitelist.

```bash
sources=()
git ls-files -z -- '*.py' ':(exclude)tests/**' ':(exclude)assets/**' > .venv/vulture-sources.nul &&
mapfile -d '' sources < .venv/vulture-sources.nul &&
.venv/bin/python -I -B -m vulture --config pyproject.toml "${sources[@]}"
```

Exit 0: no findings. Exit 3: findings. Exit 1: invalid input. Exit 2: CLI error. Do not add `|| true`. For the 100% view add `--min-confidence 100`; it mostly lists required callback signatures. Before pruning: read the whole block, check decorators, string registration, serializers and tests, then record candidate, retain with evidence, or unresolved. No mass whitelists, dummy references or renames to make the report green. The first-pass baseline is `git show eb188ac:phase-II_v2/VULTURE_BASELINE.txt`.

## Builds

`scripts/build_for_human.sh` builds `dame-curie-app:<sha>` from a committed Git archive with the V2 engine; it does not deploy. Do not run build or lifecycle scripts for discovery or `--help` in a source task.
