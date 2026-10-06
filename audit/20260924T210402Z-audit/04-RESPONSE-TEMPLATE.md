# 04 — Response template for the implementing agent

Copy this file to `05-IMPLEMENTER-RESPONSE.md` in the same folder and fill it in. Keep one block per
finding ID from `01-AUDIT-REPORT.md`. Do not delete findings you disagree with; mark them `push-back`.

Rules that make round two fast:

- `fixed` requires a local commit sha whose diff touches the cited anchor, plus the exact QA selection
  you ran (or "not run, source-only" if root has not granted an isolated test environment).
- `push-back` requires a file:line counter-argument showing the control flow the auditor missed, or a
  quoted root instruction that settles the scope. "Intentional" alone is not a counter-argument.
- `deferred` requires a named owner or ledger location (TODO.md line, STATUS.md section) where the item
  now lives, so it stops being an unowned defect.
- Do not renumber findings. Add new items you discovered under "Implementer-raised items".

---

## Finding <ID> — <short title>

- **Disposition:** fixed | push-back | deferred | no-change-needed
- **Commit(s):** `<sha>` (or none)
- **What changed / why not:** <2–6 sentences>
- **Verification performed:** <exact test selection / static review / none> — say plainly if nothing ran
- **Deployment effect:** none | built, not deployed | deployed at <UTC> under <grant>
- **Questions for the auditor:** <optional>

---

(repeat per finding)

---

## Implementer-raised items

- <anything you found while fixing that the auditor should check in round two>

## Open questions for root

- <settled-scope questions you could not decide under AGENTS.md; keep concrete>
