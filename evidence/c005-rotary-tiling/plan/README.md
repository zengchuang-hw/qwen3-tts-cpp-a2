# C005 A2 qualification

Prior RFC: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/10
Delivery: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/11
Tested source T: `547270db4d41602f868dddb0f8c406858c17d29c`;34 canonical non-evidence files, fresh Release build.
Source/binary manifest: ../patch/source-manifest.json; exact formal argv and
frozen environment/gates: formal-plan.json. Later evidence additions do not
change these34 blobs. Full formal campaign and assessor both actually exited0;
envelope confirms COMPLETED/PASS and unchanged source/binary/model/environment.

## Full fixed-upstream comparison

Upstream b4451682abac651f26046f8d27467de3f007e1e7, saved optimized command;
model0c0e3051f131929182e2c023b9537f8b1c68adfe, BF16 and11 asset hashes.
Physical910B3 card3/logical0, same card and environment for both arms. Actual
host PID2015715 / container PID89884 / final r3-native lifecycle matches card3.
No profiler in timed runs. Workload128 SHA256
5007716c83b29d0247b2c6291b9704c652e01a94362c19e90ea3cb34987060c7.

AB/BA/AB, C1/2/4/8/16/32/64,128 timed requests per cohort, warmup max(2,C).
All5,376 timed requests completed real stop/EOS; all2,688 candidate actual PCM
match their paired reference and streams reconstruct full audio. Six server
lifecycles and all42 benchmark processes exited0. Subjective quality/ASR/speaker
scoring are not claimed; exact PCM establishes relative equivalence here.

|C|Reference mean¡Àsample SD frames/s|Candidate mean¡Àsample SD|Strict TP gain|Worst p95 TTFA change|Gate|
|---|---:|---:|---:|---:|---|
|1|61.82 ¡À 2.34|71.14 ¡À 0.26|+11.39%|-6.56%|PASS|
|2|95.76 ¡À 3.57|107.48 ¡À 0.38|+9.04%|-8.34%|PASS|
|4|156.83 ¡À 2.04|174.97 ¡À 0.49|+10.23%|-11.92%|PASS|
|8|239.27 ¡À 8.83|268.89 ¡À 1.48|+8.10%|-16.96%|PASS|
|16|343.97 ¡À 13.85|393.51 ¡À 3.31|+9.07%|-23.27%|PASS|
|32|443.86 ¡À 19.79|495.67 ¡À 3.40|+7.55%|-1.54%|PASS|
|64|562.66 ¡À 27.45|635.53 ¡À 2.23|+9.16%|-3.61%|PASS|

Each side n=3. Strict gain=min(candidate TP)/max(reference TP)-1; p95 change=
max(candidate p95)/min(reference p95)-1. All strict TP ratios >1.05 and all p95
ratios <=1.05. Mean/SD are descriptive, not confidence intervals. Raw p50/p95,
RTF and all per-request data are in ../results/formal/. This is a scoped local
performance PASS, not final owner/independent project acceptance or production
qualification. Historical C002 FAIL remains unchanged.

## Mechanism, controls and boundaries

Only paired predictor rotary head tile changes4/8/16; same FP32 operations,
fusion disabled, final BF16. Initial320 exact checks and all40 three-sample L1
groups are retained in ../selection/. Policy frozen before full-model runs:
D128/B>=16/L1or2 selects16, else4. Fixed8 is slower than16 at selected high-B
points; small batches keep4 as predeclared. Default remains4.

Fresh final-source validation:14 commands exit0; CPU8, ownership4, old rotary32,
new tiling320, normal and cancellation/reuse each4 exact complete WAVs plus
stream/callback timing/guard witnesses, CLI16 complete WAVs, intentional callback
exception cleanup with0 completed requests. See ../results/local/validation.json.

Causal pilot, same native source and inline delivery, tile4 versus auto, one
pair C4/16/32/64¡Á128:512 candidate PCM exact. TP changes+0.02/+1.34/+1.42/+1.12%;
p95 changes+0.38/-1.42/-1.91/+0.63%. All prior local nonregression gates pass.
This is much smaller than45¨C64% operator latency reduction; it is not a claim
that tiling alone causes the total upstream improvement. A separate upstream
pilot has all512 candidate PCM exact, TP gains9.13/10.38/9.35/11.18%, with all
p95 improving. Both pilots retain their INCONCLUSIVE global coverage verdicts.

Qualified HTTP options are --predictor-rope paired --rotary-head-tile auto
--audio-delivery inline --prewarm-decode (max batch64, codec batch4, chunk8).
serve.py is the Python HTTP/load/capture adapter; the frame/state/graph/codec/PCM
execution core is C++. qtts remains complete-WAV mode; no CLI streaming-latency
claim. RMS fusion, precision changes, async codec queues and chunk/batch retuning
are deferred. Predictor coefficient caching RFC12 is a proposal, not part of
this frozen candidate. Held-out/stability RFC13 and final independent/owner
acceptance remain separate; do not close parent RFC3 from this performance PASS.

## Retrievable raw artifacts

archive-manifests.json has container/host paths, exact SHA256 and byte counts.
Git retains complete cohort results.json, run/lifecycle/source/env and command
logs. Redundant per-request sidecars including warmups remain unchanged in raw
metadata tars; all actual WAV bytes remain in raw media tars on A2. The formal
archive has6,144 WAVs including768 warmups; these are not6,144 timed requests.

The source is under /home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/c005-selected;
formal under sibling c005-formal. Use the same SSH key/user/host from the A2
skill to retrieve archive-manifests.json paths with scp, verify SHA256, then
extract. The archives are evidence, not reconstructed audio or imported reports.
Clock-skew/optional-library warnings stay in logs. Two device-metadata collection
attempts (host directory permission, pre-persist lifecycle PID) are retained;
the corrected live mapping succeeds and matches final lifecycle PID. No model,
source or benchmark setting was changed by those metadata retries.

Validator-source-map in ../patch/ records raw uploaded versus canonical Git LF
script hashes. The formal envelope hash in formal-plan.json covers the exact
raw archived upload; Git newline normalization is explicitly mapped, not
reported as a new A2 execution or a changed runtime source identity.
