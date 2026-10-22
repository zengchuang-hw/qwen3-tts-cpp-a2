# C009 frozen plan — codec batch granularity 4 vs 8

RFC: [#22](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/22), created
2026-10-22T04:52:24Z, before this branch existed.
Claim: [#22 comment](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/22#issuecomment-6333036474).
Review rulings: tts-SE review of the execution plan (relayed 2026-10-22), applied
below verbatim before any measurement.

## Scope

Configuration plumbing only. No change to `native/runtime.cpp`, to codec grouping,
incremental lengths, sampling or defaults.

- `campaign.py`: `--codec-batch-size` (default 4, bounded `[1,8]`) appended to the
  shared `serve.py` construction, so both arms of a native-engine campaign carry
  the same granularity. The frozen upstream command is not touched.
- `probe.py`: native arm threads the knob; the pinned upstream reference arm keeps
  codec batch 4 and rejects any other value with a parser error.

## Frozen measurement configuration

- Host/container: `zhuangzeliang@8.92.7.131`, container
  `zc-qwen3-tts-cpp-20261019`, physical card 3 (`ASCEND_RT_VISIBLE_DEVICES=3`),
  serial with other jobs, `/work/c009`.
- Source: branch `codex/c009-codec-batch`; fresh Release build in `/work/c009/build`.
- Model: `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` revision
  `0c0e3051f131929182e2c023b9537f8b1c68adfe`.
- Reference checkout: `InferMatrixLab/qwen3-tts-engine@b4451682abac651f26046f8d27467de3f007e1e7`.
- Workload: `evidence/campaign-20261017/plan/workload-128.jsonl`, SHA256
  `5007716c83b29d0247b2c6291b9704c652e01a94362c19e90ea3cb34987060c7`.
- Per campaign: `--concurrencies 16 32 64 --requests 128 --repetitions 1
  --reference-engine native-buffered --predictor-rope paired --rotary-head-tile
  auto --audio-delivery inline --codec-batch-size {4,8}`.

## Arm selection (tts-SE ruling, item 3a)

`--reference-engine native-buffered` forces the campaign's own reference arm to
`--audio-delivery buffered` while the native arm keeps `inline`. A campaign-internal
reference-vs-native delta therefore compares delivery modes, not codec batch.

- Two campaigns, `codec4` and `codec8`, both with `--audio-delivery inline
  --reference-engine native-buffered`.
- C009 compares **only the `r1-native` arm of each campaign** (inline@4 vs inline@8).
- The `r1-reference` arms (buffered) are retained for process/lifecycle evidence
  only; they are **not** a C009 comparison basis and any campaign-internal
  assessment gain number must not be cited as a C009 result.
- `--requests 128 --repetitions 1` makes `formal_coverage=false`, so
  `assessment.json` is expected to be INCONCLUSIVE. That is recorded as expected,
  never presented as an acceptance, and never extrapolated to the seven-cohort gate.

## Gates (frozen before measurement)

1. Local CPU contracts (29 frozen at the #22 baseline comment: 25 existing plus 4
   new; only additions allowed) plus syntax/diff review.
2. A2 fresh Release build exit 0; 4 compiled ownership tests succeed.
3. Exactness, cross-campaign same arm: inline@4 vs inline@8 equal per-file SHA256
   for every `(cohort, index)` over C16/32/64 x 128. Any difference is FAIL and
   stops the campaign.
4. Local non-degradation, recorded under the frozen n=1 rule below: throughput
   ratio(8/4) per cohort together with the real codec-due and ordinary-frame time
   distributions. The n=1 thresholds decide the recorded conclusion level; they
   never turn an unresolved comparison into an accepted one.
5. Budget gate: one standalone `batch=8` server start, stop at readiness, record
   `_capture_codecs` wall time and `max_memory_allocated` delta. Readiness beyond
   12 minutes stops the iteration as INCONCLUSIVE.
6. AB (4 then 8) is mandatory. BA (8 then 4) is added only if AB finishes within
   30 minutes; otherwise the report states "AB only, no order control".
7. Any capture failure must raise; no silent fallback to 4, and no record deletion
   or rerun to hide a failed attempt.

Wording boundary: gate 4 is a pilot "local non-degradation" result only. It is not
a throughput conclusion and not a performance acceptance. The formal seven-cohort AB/BA/AB gate
(min(candidate TP)/max(reference TP) > 1.05, max(candidate p95)/min(reference p95)
<= 1.05) remains separate under #3.

## n=1 conclusion rule (tts-SE addition 1, binding)

Each arm has exactly one campaign, so every cohort ratio(8/4) is a single
observation without a repeat or an order control. The conclusion level is fixed
before measurement:

| Cohort ratio(8/4) | Recorded conclusion |
|---|---|
| > 1.02 | "worth taking to the formal seven-cohort gate" only; never an acceptance |
| 0.98 - 1.02 | INCONCLUSIVE: "this n=1 run could not separate the two" |
| < 0.98 | degradation FAIL; stop, no follow-on promotion |

The overall record uses the worst cohort. If only AB ran (BA skipped by the
30-minute budget condition), the README states n=1 with no order control and the
same thresholds apply; a favourable-looking number never upgrades the level.

## Secondary consistency check (tts-SE addition 2, zero extra card time)

Both campaigns also emit a buffered arm. A buffered@4 vs buffered@8 per-file
SHA256 comparison over C16/32/64 is reported as independent evidence that the
codec batch does not change audio. A buffered-arm difference that the inline arms
happen to hide is reported as a defect, never as noise.

## Environment snapshots (tts-SE addition 3)

`npu-smi` on card 3 (AICore%, HBM, temperature), the container ID and a
concurrent-job check are captured immediately before and after each campaign.
Baseline reference is 3419 MB HBM / AICore 0%; any deviation is explained.

## argv traceability (tts-SE addition 4)

The PR body pastes the two campaign argv and the two serve argv verbatim. They
must match `runspec.json` and `lifecycle.json` on `--audio-delivery inline` and
`--codec-batch-size 4|8`; a mismatch between narrative and evidence is a
blocking defect.

## PR wording red lines (tts-SE addition 5)

Even above 1.02 the PR may only say "the pilot observed 8 above 4; the formal
seven-cohort gate is required". Performance-acceptance wording, any
percentage-improvement conclusion, or a qualitative comparative claim are
forbidden. An INCONCLUSIVE record may not be restated as "ruled out" or "no
impact" - only as "this n=1 run could not separate them".

## Deviation record (kept next to the plan, not after it)

1. **`max_memory_allocated` not collected.** Gate 5 above asks for it before and
   after capture. This round did not sample it: the timing wrapper logged only the
   capture wall clock. The number is recorded as not collected, not estimated and
   not back-filled. Substitute evidence is the card-3 device-side HBM series in
   `results/gate/README.md`, which is labelled as device-side allocated HBM and is
   never described as a torch allocator peak. Lesson for the next iteration:
   instrument allocator peak sampling before the capture run starts.
2. **Cold-versus-warm capture, corrected after measurement.** The 508.018 s capture
   in the gate run is a cold first-run figure that includes Triton compilation; the
   two campaigns together took 8 min 04 s, so the iteration stayed inside the
   45-minute budget. An earlier draft prediction of a structural overrun is
   therefore withdrawn as measured wrong, and is kept visible rather than deleted.
   The improvement idea still stands for other reasons: an arm-selection switch in
   `campaign.py` (for example `--arms native`) would stop a pilot paying for the
   buffered arm that ruling 3a discards.

## Recomputability (tts-SE requirement)

Every delivered number must be recomputable by tts-SE from raw per-request records
(cohort, index, timestamps, throughput, PCM SHA256 with a resolvable file path),
not from `assessment.json` aggregates. Any aggregate that disagrees with the raw
records is treated as a defect.

## Evidence layout

`evidence/c009-codec-batch/{plan,results,patch,validator}/` — plan (this file),
results (identities, lifecycle, per-request records, PCM comparison, capture timing
and memory), patch (diff), validator (comparison scripts and outputs).
