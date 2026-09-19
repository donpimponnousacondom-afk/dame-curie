# Static dead-code audit — soft landing

## Tool and scope

Use **Vulture 2.16**, pinned in `requirements-dev.txt`, with the existing Python **3.14** interpreter boundary. Its [release metadata](https://pypi.org/pypi/vulture/2.16/json) declares Python 3.14 support. It complements Ruff's existing unused-name checks; coverage/runtime reachability is a different, later assignment.

Vulture parses source with `ast`; it does not import the audited application. The verified tool reads its own bundled whitelists, not the application's imported packages. Its analysis is name-based and ignores scopes: repeated names can hide dead code, while framework callbacks, serialization and external consumers can create false positives. A finding is **not** deletion authorization or a production-usage measurement.

The current policy is **report only**: `min_confidence = 60`, size-sorted output, no added project suppressions or generated whitelist, no pre-commit/CI failure gate, no autofix. Scores are category heuristics, not measured probabilities. Even a 100% unused-argument report does not mean a callback parameter can be removed.

## Isolated installation

Environment creation/installation requires an explicit tooling assignment; loading a skill is not that assignment. Root supplied it for the initial audit. A new checkout's Python 3.14 venv procedure is in `DEVELOPMENT.md`. Never replace an existing environment or install into system Python.

For the verified tool-only environment, from the checkout root:

```sh
.venv/bin/python -I -B --version
.venv/bin/python -I -B -m pip --isolated --disable-pip-version-check install --only-binary=:all: --no-deps --index-url https://pypi.org/simple vulture==2.16
.venv/bin/python -I -B -m vulture --version
```

On Python 3.14, this Vulture release has no required third-party runtime dependency; its conditional `tomli` dependency is for older interpreters. Do not install the entire development/application requirements merely to run this audit. The local `.venv` initially contains this audit tool and bootstrap pip, not a ready-to-run application environment. `-I` avoids the checkout/PYTHONPATH and user site as import sources; do not activate or source private configuration.

## Select source explicitly

Use Bash **from the checkout root**. Select tracked Python source only; do not run `vulture .`. Tests and the deep harness are intentionally excluded from this production-source inventory, not declared unused. Runtime data, generated public sites, archives, dependencies, dot-directories and concurrent scratch work are outside the scan.

```bash
sources=()
git ls-files -z -- '*.py' \
  ':(exclude)tests/**' ':(exclude)deep_test_harness.py' \
  ':(exclude)legacy/**' ':(exclude)assets/**' \
  ':(exclude)phase-II_v2/**' ':(exclude)scratch-mermaid/**' \
  ':(exclude)data/**' ':(exclude)data_gf/**' ':(exclude)public/**' \
  ':(exclude)temp/**' ':(exclude)shelldocker/**' ':(exclude)logs/**' \
  ':(exclude).*' > .venv/vulture-sources.nul &&
mapfile -d '' sources < .venv/vulture-sources.nul &&
printf '%s\n' "${sources[@]}"
```

Review the printed paths and require successful selection before continuing. The ignored `.venv/vulture-sources.nul` is a temporary path inventory, not configuration. The array starts empty and is populated only after Git succeeds, so partial Git output is not accepted. Do not hide the Git producer inside process substitution, whose failure would not propagate through `mapfile`.

Then, in the **same Bash session**:

```bash
.venv/bin/python -I -B -m vulture --config pyproject.toml "${sources[@]}"
```

`pyproject.toml` deliberately has no default `paths = ["."]`; an empty path list is rejected by the verified Vulture version rather than falling back to a recursive scan.

For the higher-confidence view, retain the same `sources` array and add `--min-confidence 100`. This is a view, not a better safe-deletion oracle: in the first pass it predominantly selected necessary callback signatures. Lower-confidence ordinary private helpers can be more useful cleanup leads.

Exit statuses: **0** no findings; **3** findings produced; **1** invalid input/syntax/encoding; **2** CLI/configuration error. Keep stderr and investigate errors. Do not use `|| true` to turn every failure into an apparently successful audit. In a soft pass, exit 3 is an expected report outcome, not a failed application test.

The initial manifest/report are `phase-II_v2/VULTURE_INPUTS.txt` and `phase-II_v2/VULTURE_BASELINE.txt`. They are a dated source snapshot; regenerate the selection after source additions/removals rather than silently ignoring missing files. Do not overwrite that baseline merely to make counts improve.

## Triage before pruning

1. Read the whole reported function/block and check the real caller/replacement. Prefer ordinary orphaned helpers and demonstrably retired code over deleting event callbacks or configuration fields.
2. Check decorators, inheritance, string/dynamic registration, serializers, platform interfaces, CLI entrypoints and relevant existing test references. Do not execute them to answer a static question.
3. Record **candidate**, **retain with evidence**, or **unresolved**. An unused parameter body does not make its signature disposable. An unused configuration attribute does not establish that its environment name has no other consumer.
4. Preserve shared dependencies and manual compatibility patches. No mass whitelist, blanket decorator suppression, dummy references or unused-name renames to make the report green. Suppressions, when later warranted, require specific evidence.
5. Use the explicitly approved removal scope: `phase-II_v2/REDESIGN_PLAN.md` now authorizes the Discord-only cuts, not arbitrary deletion of Vulture findings. Verify the assigned diff; rerun an audit only under a compatible tooling grant. Tests/runtime validation still require their separate isolated assignment. No new tests are authorized.

Initial results and reviewed examples: `phase-II_v2/DEAD_CODE_PASS.md`. Vulture does not establish code coverage, actual enabled features, runtime reachability or a percentage of removable LOC.
