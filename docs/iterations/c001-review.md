# C001 migration review

Reviewed the C++ event loop, C API, ownership/compaction, graph readiness checks,
PCM writes and standalone evidence tests before opening the PR.

- All 12 source files in the measured C001 identity match the migrated bytes.
  The archived pre-Git binary remains identified by its SHA256; this PR does not
  claim the existing binary was built from the later Git commit.
- Local CPU suite: 3 tests passed. Python syntax compilation and diff whitespace
  check passed. These are synthetic evidence audits without torch/NPU imports.
- Remote build, three ownership tests and bounded NPU probes were completed
  before migration; their logs/identities are retained. A clean build in the new
  repository path was not run for C001.
- The exploratory timing is explicitly unqualified because of libc6 drift and
  incomplete repeat/concurrency coverage. No objective-level PASS is asserted.
- In this revision the public HTTP protocol can request an output bound larger
  than the allocated native arena; the native core rejects admission. C002 must
  reject this at the HTTP boundary before enqueueing. This is a known prototype
  limitation, not a production-ready server claim.
- Native `Runtime` and its pointer C API assume the trusted graph/bootstrap
  adapter provides tensors with correct shapes and lifetime. They are internal
  interfaces, not a public arbitrary-tensor API.

Decision: eligible to merge as the documented C001 research baseline after CPU
CI passes, with performance INCONCLUSIVE and the listed limitations retained.
