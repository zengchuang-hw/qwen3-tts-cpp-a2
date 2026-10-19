# C004 inline callback validation

Prior RFC: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/8
Delivery PR: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/9

Tested source: `18a87390ef8411f627a3ce1627e5ffe986bc6d90`, canonical Git
export of 31 non-evidence files. Source was synced before execution; the actual
manifest is in `../patch/source-manifest.json`. The archived validator verifies
source before each command and at completion and compares model/runtime identity.

All 12 validation commands exited 0: CPU suite 7/7, fresh Release configure/build,
compiled ownership 4/4, rotary parity, both normal/cancellation reference/native
probes, native CLI, intentional callback error probe and the causal HTTP pilot.
The callback witnesses verify execution inside core.step, on the owning thread,
with cancel/reentry/close rejected. The intentional exception unwinds and permits
cleanup; its zero completed requests are not counted as successful generation.

Normal and cancellation cases each compare four complete actual WAVs and verify
stream reconstruction. The native CLI completes four WAVs with exit 0; it is not
a streaming CLI latency or full-corpus differential-quality claim.

The causal pilot uses the same native source/config, buffered versus inline,
C4/16/32/64, one pair and 128 timed requests per cohort. All 512 candidate PCM
match retained control audio. This is not upstream performance acceptance:
`reference_engine=native-buffered`; assessment remains INCONCLUSIVE globally.

| C | Buffered frames/s | Inline frames/s | Throughput change | Buffered p95 ms | Inline p95 ms |
|---|---:|---:|---:|---:|---:|
| 4 | 172.74 | 173.04 | +0.17% | 94.46 | 92.46 |
| 16 | 394.03 | 385.22 | -2.23% | 215.49 | 206.01 |
| 32 | 490.38 | 488.32 | -0.42% | 460.08 | 442.26 |
| 64 | 628.21 | 624.54 | -0.58% | 846.94 | 831.94 |

All four cohorts meet the prior per-iteration nonregression scope (throughput
ratio >=0.95; p95 ratio <=1.05). There is no throughput-improvement claim.
Latency improvement from one exploratory pair is not a repeated L4 claim.
The default remains buffered and the overall frozen upstream gates are unchanged.

Raw full audio archive:
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/c004/audio-artifacts.tar`;
SHA256 `7fce54aeab0302c769b02ce68756fea1e43226bde9222a125070c29c161d5ad1`,
296,427,520 bytes. Original source, build and raw request/exit logs remain in
that isolated c004 directory. `../results/validation.json` retains commands,
true exits, binary hashes, model/runtime and local-scope outcomes. Assessment
reads actual WAV bytes. No failed requests, cancelled probes or missing scorer
outputs have been relabeled as a global PASS.
