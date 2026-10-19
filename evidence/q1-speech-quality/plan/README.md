# Q1 actual A2 evidence

Delivery qualification: **PASS for evaluator tooling**. Independent candidate
quality in the forced-scoring run: **INCONCLUSIVE**, not runtime acceptance.
Prior design and amendments: [RFC #17](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/17),
preserved in `rfc-17.json`. C007/PR #15 and C008 remain unresolved.

Tested source T: `359ef11088aa6ac42ba685af449091190d1f9ca6`.
Base: `0e91716c3af1f44f63c46a9c0342cb0c7254758d`.
All 40 canonical Git source files are listed in `../patch/source-manifest-05.json`.
Evidence-only commits after T do not change those runtime/scorer sources.
Actual Release binary SHA256:

- `_qtts_native.cpython-312-aarch64-linux-gnu.so`:
  `75ce6d3979d0794eb2fb3a3ede330997df25ed20c3e691339025c9e31fbefaee`.
- `qtts`: `b16ff9a8ff9af5f6fa4f1c9855cca98e42d9e2ceba5cbc38152783061d45bd17`.
- Pre-generation freeze:
  `8c22b23504e4e906e44e934f5b3fb86b8379fef7a08a370142a316b8e78cfb76`.

## Machine, sources and actual checks

SSH `zhuangzeliang@8.92.7.131`, dedicated container
`zc-qwen3-tts-cpp-20261019`, image
`sha256:e78fc581345117b32007a0ba7c337e06ac71df8200bbe609142f294c18f42dc3`.
Container `/work` maps to host
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019`.
Physical 910B3 card 3 maps to logical `npu:0`; the active driver witness matches
host PID 2407338 to container/native lifecycle PID 99636. See
`../results/control/q1-device-witness05/witness.json` and its raw driver snapshot.
Earlier one-off witness attempts did not establish an active match and are not
used as hardware proof. No unrelated NPU process was stopped.

`/work/q1-attempt05` holds the tested source/build/generated/scores. Preparation
ran CPU contracts (20), fresh CMake Release configure/build and compiled ownership
tests (4), all actual exit 0. **The ownership tests use CPU tensors on the A2
machine; they are not NPU graph-replay tests.** This corrects an early PR progress
comment. The complete HTTP TTS generations are the actual NPU evidence.

`freeze --score-all` verified the clean reference at
`b4451682abac651f26046f8d27467de3f007e1e7`, TTS model
`0c0e3051f131929182e2c023b9537f8b1c68adfe`, canonical source/binaries, runtime,
heldout workload `51ee03d4ed7d893045c64ea8944a5edc2dd59fc93a202f0419bced624ff49d0d`,
and all 14 evaluator assets before a new generation boundary. Whisper-small
revision `973afd24965f72e36ca33b3055d56a652f456b4d` and WavLM-base-plus-sv revision
`feb593a6c23c1cc3d9510425c29b0a14d2b07b1e` ran on CPU float32/eager with four
threads. The full package/Python/library/environment locks are in `freeze.json`.
The A2 direct Hub download timed out; its setup log is retained. The same pinned
public bytes were downloaded on the desktop, transferred successfully and
verified again on A2. Audio was not sent to an external inference API.

Actual commands/true exits/log hashes are under
`../results/attempt-05/results/{prepare,evaluate}/validation.json` and the
follow-up records. The source and all TTS/evaluator assets/runtime/binaries
remained equal to the freeze. Windows source mtimes were approximately 116
seconds ahead of A2; tar/CMake clock-skew warnings remain in the logs. No clocks
were changed, and content/binary SHA verification did not use mtime as identity.

## Outcomes and retained failures

| Attempt | Actual outcome |
|---|---|
| 01, source 1be5583 | CPU15/build/compiled CPU ownership pass; no accepted quality generation. |
| 02, source 844bc2e | CPU16/build/compiled CPU ownership pass; old-audio CPU API diagnostic only. |
| 03, source 3fac48c | New 128 timed requests, both servers exit0, 64 exact pairs. Exact route correctly skipped scorer; required controls exit1 for no new score records. Envelope FAIL retained. |
| 04, source 6b1f193 | New complete generation and exits0; forced scoring aborted on ASR completeness. INCONCLUSIVE retained. The original implementation did not retain that invalid raw record; it is not reconstructed as new evidence. |
| 05, source 359ef11 | New 128 timed requests, both servers exit0, all64 actual PCM pairs exact. All64 pairs graded: 62 valid, 2 ASR-limit INCONCLUSIVE. Initial negative checker selected a pair summary instead of a raw score and exited1; original envelope FAIL remains unchanged. |
| 05 follow-up | Corrected checker selects raw records with pcm_sha256/asr/speaker; the same ten mutations all reject, actual exit0. A2 replay audits every waveform, raw score/error, pair, group, source/asset lock and physical PID mapping; CPU20 repeats exit0. Tool qualification PASS, candidate independent quality INCONCLUSIVE. |

Both incomplete records are English workload index4, one per concurrency. The
actual retained windows hit 444 new tokens (including a 5.36-second C4 input);
no token limit, EOS or coverage gate was relaxed. Each affected English group is
INCONCLUSIVE, without acceptance on its remaining 15 records. Complete Chinese
groups have identical candidate/reference errors: C4 104/357 (29.13%), C16 99/357
(27.73%), delta 0. These absolute error rates are not hidden. All candidate pairs
were exact PCM, so candidate model results reuse only the identical reference
PCM's real scores. No real nonexact-pair speaker acceptance is established by
this run, and C007's original eight nonexact outputs are not retroactively passed.

See `../results/attempt-05/followup-validation.json`, `scores/assessment.json`,
the 64 pair records and raw model token/transcript/window/embedding records.
Follow-up preserves original envelope SHA
`8442b66fdbf7555582d511f8158ad930a63c25eb64f473b27e7868750e9eec80`.
Checker correction changed record selection only; inference, cached actual
outputs, source T, scoring math and all ten rejection conditions stayed fixed.
It did not re-run or relabel an old TTS experiment.

This delivery establishes evidence-tool behavior. It does not establish new
speed, subjective naturalness, absolute speaker identity, production stability,
or a fix for C008. C005's separate frozen full performance result is unchanged.
Additional final independent review/owner acceptance remains pending.

## Raw retrieval and Git curation

`archive-manifest.json` records all archives, attempt outcomes, validator and
media hashes. On A2 under `/work/q1-evidence-20261019/` (same host-mapped suffix):

- `metadata.tar`: 8,857,600 bytes / 1,050 files,
  SHA256 `dee45c9b5a6228a950fef06df5ba291bb060ee89b09350a5cdf7420ce3dd1298`.
- `media.tar`: 202,383,360 bytes / 504 WAVs from the three new generations,
  SHA256 `fb870f553bce9fcafeaaada97a24d299deacaf26119fb011ee315205ff5900f3`.

Git keeps aggregate cohort request records, every actual independent model/pair
record, freezes, commands, exits and logs. Only redundant five-digit request
sidecars are omitted from Git; all remain in the unmodified metadata archive.
Public model weights stay on A2 and are reproducible from pinned asset hashes.
Old-audio compatibility probes reference C007's separately preserved media and
explicitly disallow retrospective acceptance.

Raw uploaded validator CRLF bytes are preserved in the archive. Git normalizes
them to LF; `../patch/validator-source-map.json` maps both SHA256 identities.
These are evidence scaffolds, not public runtime configuration files.
