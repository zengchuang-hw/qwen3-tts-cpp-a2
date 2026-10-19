# Mandatory pre-merge review

Authority: owner instructions on 2026-10-19, [process RFC #4](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/4)
and the binding amendment to [roadmap #3](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/3).
Only the first init PR (#1) has the A2-evidence exception. This process PR itself
must meet these rules. They apply to documentation, tooling and CI changes too.

Before creating an iteration PR, record its RFC: problem, scope, one hypothesis,
alternatives, affected consumers, validation commands/levels, frozen gates and
evidence plan. A broad roadmap or a design written after PR creation does not
establish design-first ordering. Link material design updates before changing scope.

Run the checks specified by the RFC on the A2 host against the intended source.
For runtime/kernel changes include the affected build, operator/state, complete
generation and performance/quality checks. For docs/process-only changes run
relevant content/control checks on A2 and state that no NPU inference was tested.
Neither a reachable host nor `npu-smi` alone validates a change.

## Required review comment

Actually inspect the diff and evidence, then copy this template into a **comment
on the PR**, filling every row separately. Do not precheck it in the PR body.
State the reviewer identity and whether this is author self-review or independent
review; do not relabel self-review. Additional RFC-required independent review
must be completed separately.

```markdown
## Pre-merge review — <reviewer; role; self/independent>

PR: <url>
RFC: <url; design recorded before PR timestamp>
Reviewed head H: <full SHA>
Assessed base B: <full SHA>
A2 tested content T: <full commit + source/binary manifest>
T -> H applicability: <diff and why evidence remains applicable, or refreshed run>
A2 evidence: <committed manifest/log links + retrieval path>

| Item | Result | Finding and concrete evidence |
|---|---|---|
| R01 RFC exists before PR; scope and gates are clear | PENDING | |
| R02 Scope/alternatives and affected consumers match the actual diff | PENDING | |
| R03 Implementation reviewed: correctness, bounds, ownership, errors and cleanup | PENDING | |
| R04 Actual A2 host/container/device/environment identity established | PENDING | |
| R05 Tested source/binaries and current H/B applicability verified | PENDING | |
| R06 RFC-required A2 commands completed; true exits and retrievable logs exist | PENDING | |
| R07 Required correctness/state/quality checks passed; missing checks disclosed | PENDING | |
| R08 Required performance gates and all cohorts audited, or scoped N/A justified | PENDING | |
| R09 Evidence is complete for claims; failures/skips/drift remain visible | PENDING | |
| R10 CPU CI and required repository checks passed | PENDING | |
| R11 Required reviews/findings resolved; DCO, attribution and no unrelated changes | PENDING | |
| R12 Final H/B, evidence, review comments and merge authority rechecked | PENDING | |

Decision: BLOCKED / MERGE_ELIGIBLE
Remaining blockers: <explicit list or none>
Scope of accepted result: <what this PR proves; separate from overall goal>
```

Each row uses PASS, FAIL or INCONCLUSIVE; N/A needs a concrete per-row reason
under the RFC. PENDING is only an uncompleted review placeholder. RFC ordering,
actual A2 validation, source applicability and this comment cannot be waived by
N/A. A required item not met blocks merging. A blanket "all checked" is invalid.

R04 must distinguish checks executed on an A2 machine from checks actually using
its NPU. R06 must retain nonzero exits; never turn an interrupted, partial or
missing run into PASS. R07/R08 use the frozen RFC acceptance scope: recording a
failed optimization is not the same as accepting that optimization as faster.
Any evidence-only research scope must be designed beforehand, not invented after
a failing measurement.

## Evidence freshness and integration

- Bind the review to full H/B/T identities. Historical experiments require an
  explicit content/environment mapping; a copied binary is not a fresh build.
- When code, base, environment or validator changes, inspect the delta and refresh
  affected checks and review rows. A new evidence-only commit may reuse a run only
  with an explicit reviewed applicability explanation.
- Immediately before merge, re-read the current head/base and required checks,
  verify the review comment still applies and no required findings remain open.
- Preserve DCO and assistance attribution during integration. Do not automatically
  close a parent goal or label its performance PASS because a PR merged.
- Historical PR #2 was opened before its RFC. Keep that gap visible and do not
  merge it under a retroactive design-first assertion; use a replacement PR.

These are execution rules. At adoption, GitHub returned HTTP 403 for branch
protection on this private repository's plan. No platform-enforced protection is
claimed; repository privacy and account plan are unchanged.
