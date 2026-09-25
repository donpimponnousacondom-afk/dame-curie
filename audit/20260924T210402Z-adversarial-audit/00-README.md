# Adversarial audit — dame-curie `dev/phaseII_v2` @ `c603cf2`

Folder: `audit/20260924T210402Z-adversarial-audit/` (UTC timestamp of audit start). The parent `audit/`
directory is gitignored (`.gitignore:138`); nothing in this folder is meant to be committed. This folder is
self-contained; it does not modify or reorganise the older loose files in `audit/`.

Audience: the agent in charge of the V2 port/implementation (the "implementing agent"). No human is
expected to read this in full. Root's AGENTS.md contract applies to everything proposed here; nothing in
this folder is a runtime, deployment, test-execution or provisioning grant.

## Files

| File | Purpose |
| --- | --- |
| `01-AUDIT-REPORT.md` | **Start here.** Ranked findings with file:line anchors, failure scenarios, smallest fixes, process findings, and the auditor's advice on what to cut. |
| `02-EVIDENCE.md` | Facts the coordinating auditor verified personally (tree hashes, timelines, constants, control-flow anchors) and ledger claims that could not be verified under the boundary. |
| `03-DISPOSITIONS.md` | Every child-agent finding with the coordinator's verdict: accepted, downgraded, rejected, or merged — so the implementing agent knows which child claims to trust. |
| `04-RESPONSE-TEMPLATE.md` | Structured template for the implementing agent's answer: per finding, `fixed` / `push-back` / `deferred` with commit sha and rationale. Filling it in is what makes round two tractable. |
| `child-reports/` | Verbatim reports from the five read-only review agents (provider path, tool-loop economics, image/config/taint/longprompt, Dirac runtime and log console, docs/process). |

## How this audit was run

- Coordinator: Claude Fable 5.1 (this session). Children: two Fable, two Opus, one Sonnet review agents,
  all read-only, all given the AGENTS.md safety boundary verbatim. AGENTS.md names DeepSeek V4.1 Flash and
  GPT-5.6 Luna for these roles; neither was available in this harness. This is a recorded deviation, not a
  claim of equivalence.
- Method: orientation on `docs/`, `phase-II_v2/`, `TODO.md`, the ignored `audit/` ledgers and the last 40
  commits; full diff reading of the eight source commits since `e4e4582`; control-flow tracing of the
  provider/tool-loop path; independent child reviews; coordinator verification of every child finding that
  is ranked high or above before inclusion.
- Boundary: no application import/execution, no tests, no Docker/Screen/service access, no private
  configuration, state, log or backup reads, no `legacy/` reads, no Git writes.

## Round-two protocol (proposed)

1. Implementing agent evaluates `01-AUDIT-REPORT.md`, fixes what it accepts, and fills
   `04-RESPONSE-TEMPLATE.md` (push-backs need a file:line counter-argument, not a restatement of intent).
2. Root/handler returns the filled template plus new commit shas to the auditor.
3. Auditor re-verifies the diffs of the cited shas only, answers push-backs, and writes
   `05-ROUND2-REPORT.md` with closure points into this same folder.
