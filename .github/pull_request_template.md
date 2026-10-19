## Prior RFC and scope

RFC: <link; its design must be recorded before this PR is created>
Iteration, hypothesis, affected consumers and frozen acceptance scope:

## Problem and resulting behavior

Describe the concrete mechanism changed and why it should help.

## Alternatives

Record options considered, selection rationale and rejected/untested variants.

## Validation

Include CPU/build/operator/full-generation checks and their actual outcomes.
For performance, include exact baseline/candidate/model identities, hardware,
commands, workload, repeat/order, throughput, TTFA, RTF and retained evidence.
Keep PASS / FAIL / INCONCLUSIVE separate for each claim.

### Mandatory A2 evidence (only init PR #1 is exempt)

- A2 tested commit/content and manifest:
- Host/container/device, environment and model identity where relevant:
- Exact commands, actual exits and test counts:
- Retained logs/results, checksums and retrieval paths:
- Tested content -> current head/base applicability or refreshed validation:
- Checks not run and their impact on the RFC acceptance scope:

Docs, process and CI PRs also need relevant checks executed on A2. Local tests,
GitHub CPU CI, host availability and upstream reports do not substitute for this.

## Mandatory pre-merge review comment

Use the [itemized review checklist](../docs/pr-review-checklist.md) in an actual
comment under this PR after reviewing the diff and evidence. Fill each row with
its finding and proof; do not premark every item as passed in this template.

Review comment URL: <required before merge>
Reviewed head/base and final applicability: <full SHAs>
Unresolved required items: <blocks merge until resolved>

## Limitations and next decision

State missing checks, rejected measurements, quality scope and remaining risks.
