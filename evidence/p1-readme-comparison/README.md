# P1 publication evidence

Prior design: [RFC #20](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/20).

Scope: README publication of the frozen C005 single-910B3 comparison, not a new
NPU benchmark or new audio-quality qualification.

Tested T: `baa5fe5d5768a2e87acb84132fbf753d3af79b79`.
Base B: `f69c00c02bd590f0e1fdcd5fd19b69035570a88d`.
The 44 deployed canonical non-evidence source files are bound by
[source-manifest.json](validation/source-manifest.json). The validator is the
canonical committed T blob, verified against [input-manifest.json](validation/input-manifest.json).
The 92 historical C005 inputs are canonical Git blobs from T, already retained
under `evidence/c005-rotary-tiling/results/formal/`; this iteration does not
duplicate those request records. On A2 each was also compared to the original
`/work/c005-formal/results/` JSON; see [crosscheck](validation/original-c005-crosscheck.json).

## Actual A2 validation

Host `ascend131`, SSH `zhuangzeliang@8.92.7.131`; dedicated container
`zc-qwen3-tts-cpp-20261019`, full container/image identity in
[host-identity.log](validation/host-identity.log). Commands ran inside that
container using `/work/venv/bin/python` 3.12.13, not in the shared development
container. No NPU was allocated or measured in P1. C005 hardware applicability
comes from its retained physical-card-3 evidence, not this CPU audit.

- CPU suite: 25 tests, actual exit 0; [full log](validation/cpu.log).
- Content audit: actual exit 0; [report](validation/content.json) and
  [full log](validation/content.log). Recomputed all 42 cohort aggregates from
  5,376 requests, matched all seven README rows, 2,688 recorded PCM-hash pairs,
  six clean lifecycles, 42 zero benchmark exits, provenance, limits and links.
- [Exact argv/exits](validation/validation.json), [runtime identity](validation/identity.json),
  [executed runner](validation/runner.py) and [executed validator](validation/validator.py).
- [Local CPU log](local-cpu.log) also records 25 tests passing. GitHub exact-head
  CPU CI and the itemized review are linked from the PR.

This replay checks retained metadata and its README presentation. It does not
rehash WAV bytes, establish a fresh performance measurement, resolve C007, or
replace C005's original actual-WAV audit. No binaries were built or changed;
the historical measured binary identities stay in C005's formal plan.

## Retrieval and final-head applicability

Raw A2 metadata archive:
`/work/p1-readme/validation-metadata.tar` (host prefix
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/`), 184,320 bytes,
SHA256 `05f26f4520b7855bc6567a728eeb03b8c66aa2d575c64d7b39535a0d96aed668`.
All archive files are committed under `validation/`. The raw input bundle stays
at `/work/p1-readme/qtts-p1-inputs.tar`; its per-file hashes are in the manifest.
The archive was downloaded and its SHA256 independently matched locally.

T -> final PR head adds only P1 evidence and this evidence guide; README,
iteration design, validator and all 44 tested source files remain byte-identical
to T. The itemized PR review records final H and this mapping. It is not a fresh
run at H. Recorded raw uploaded runner/validator hashes are checked against the
canonical Git blobs before merge; any newline normalization is recorded explicitly.

An initial host-side metadata copy failed with permission denied because the
container created `validation/` as root. It did not rerun or change the tests.
Packaging was corrected by running `cp`/`tar` inside the dedicated container;
see [collection attempts](collection-attempts.json). Clock-skew warnings appeared
during transfer/extraction; [sync.log](sync.log) retains the source-transfer
warning. Source identities use content hashes, not timestamps; clocks were not changed.
