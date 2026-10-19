# Development rules

- Each iteration follows RFC design -> code PR -> A2 validation -> itemized
  review comment -> merge. Record the iteration RFC before creating its PR;
  the umbrella roadmap does not replace an iteration's design.
- Public configuration uses CLI arguments. JSON is evidence or internal data.
- CPU evidence tooling must import without torch or accelerator runtimes.
- Preserve PASS / FAIL / INCONCLUSIVE. Missing evidence is not PASS.
- Preserve exact upstream revisions, model identity and verification scope.
- Run `python -m unittest discover -s tests -v` for CPU tests; record remote
  accelerator commands, actual exits and any checks not run.
- All commits must use `git commit -s`.
- Record material agent assistance with an actual `Agent-assisted-by` trailer.
- Each iteration must use a pull request. Record the problem, mechanism,
  alternatives, validation evidence, rejected results and remaining limitations.
- The owner authorized routine iteration PR integration on 2026-10-19, subject
  to the mandatory gates below; no repeated human-per-PR permission is required.
- Only the first init PR (#1) is exempt from the A2-evidence requirement. Every
  other PR, including docs, CI and process changes, must have actual validation
  on the A2 machine before merge. Local tests, GitHub CPU CI and imported reports
  cannot substitute for it. Freeze validation scope in that iteration's RFC.
- Keep A2 commands, actual exits, environment, tested commit/source and binary
  hashes, logs and retrievable evidence linked from the PR. Match the checks to
  the changed behavior; docs-only A2 checks do not establish NPU inference speed.
- Before merging, actually inspect every item in
  [the review checklist](docs/pr-review-checklist.md), then publish an itemized
  comment on that PR with current head/base, each finding and its evidence.
  An empty checklist, blanket approval or PR-body checkboxes are insufficient.
- Missing A2 evidence, an unresolved required item, or a failed required RFC gate
  blocks merging. N/A requires a per-item reason; it cannot waive RFC order,
  A2 evidence, source applicability or the review comment itself.
- Refresh affected checks and the review comment after relevant head/base,
  environment or check-definition changes. Added evidence-only commits require
  an explicit reviewed diff/applicability mapping, not an invented fresh run.
- A research/evidence-only delivery can record a failed performance hypothesis
  only when its RFC declared that scope beforehand and its required correctness
  and evidence checks pass. Never lower gates after results or claim overall
  performance PASS from such a merge; keep unqualified optimization opt-in.
- Keep historical ordering truthful. PR #2 predates its RFC and stays unmerged;
  use a prior iteration design and replacement PR rather than rewriting history.
- Do not publish packages or activate production systems.
