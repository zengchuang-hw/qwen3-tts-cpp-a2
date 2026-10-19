# C003 validation scope

Prior design: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/6
Delivery: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/7

This is a reproducible-control and diagnosis delivery, not full performance
acceptance. Historical C002 remains FAIL. The frozen overall seven-concurrency
criteria in issue #3 are unchanged.

Tested source: `26dbebb6ff816f5108309b191e9488da4a168ce3`, canonical Git
export excluding historical evidence only. All 30 exported file bytes are in
`../patch/source-manifest.json`. Source was synchronized before testing using
the a2-run-tests sync script. The archive's validator checks those bytes before
each command and at completion, and checks actual model/runtime identities.

Read `../results/validation.json` for exact argv, real exits, fresh binary hashes,
environment/model identities and full-WAV comparisons. All mandatory commands
exited 0. The CPU suite passed five tests and compiled ownership passed three.
Thirty-two selected rotary cases matched. The normal and cancellation probes
each compare four complete actual reference/native PCM waveforms. The native
executable retained four complete WAVs and exited 0.

The B64 trace repeats index 42 from the fixed workload and retains 64 active
requests across all 16 steps. Preserve the RECORD-stop warning and diagnostic
scope: host frame spans and summed kernel accounting do not establish HTTP
throughput, a complete critical path or full-corpus quality. The failed initial
device-query command is retained; no workload ran before the corrected query.

Raw WAV/trace evidence is in the readable remote archive declared by
`../results/media-manifest.json`; retrieve from host path
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/c003/media-trace.tar.gz` and verify
its SHA256 before inspecting. Original raw results/source/build are beside it.
The large trace tree itself is container-root owned, so use that archive or
`docker exec` rather than assuming the host SSH user can read every subdirectory.

The final results-document-only delta was separately checked on A2; its exact
bytes are identified by `../results/final-doc-check.json`. Other tested source
files remain unchanged. The final PR review must bind current H/B/T and confirm
the remaining differences only add evidence and that results document.
