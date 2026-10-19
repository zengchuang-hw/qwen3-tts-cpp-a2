# Qwen3-TTS native graph runtime for Ascend

Research implementation. See [the frozen plan](docs/plan.md).
Build, complete speech correctness and end-to-end performance are qualified
separately. C005's fixed 128-text A2 comparison passed all seven concurrency
cohorts: strict throughput gains 7.55-11.39%, with all p95 TTFA improved. See
[C005 evidence](evidence/c005-rotary-tiling/plan/README.md) and
[PR #11](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/11).
This result applies to the explicitly selected paired/auto/inline options below.
The additional C007 corpus exposed an intermittent shutdown failure and eight
inexact C16 outputs; [PR #15](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/15)
remains blocked. Later exact runs do not establish a fix. Broader reliability and
final independent/owner acceptance remain open.

## Single Ascend 910B3 performance comparison

**Measured C005 configuration: 7.55–11.39% strict throughput improvement over
qwen3-tts-engine, across every tested concurrency.** These are our matched local
HTTP streaming measurements on **one physical Ascend 910B3 (card 3, logical
`npu:0`)**, not upstream-reported results. No new performance run is claimed for
current main; the table describes the frozen candidate below.

| Concurrency | qwen3-tts-engine throughput (frames/s) | This C++ runtime throughput (frames/s) | Strict throughput gain | qwen3-tts-engine p95 TTFA (ms) | This runtime p95 TTFA (ms) | Conservative p95 change |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 61.82 ± 2.34 | 71.14 ± 0.26 | +11.39% | 51.46 | 45.86 | -6.56% |
| 2 | 95.76 ± 3.57 | 107.48 ± 0.38 | +9.04% | 78.28 | 69.68 | -8.34% |
| 4 | 156.83 ± 2.04 | 174.97 ± 0.49 | +10.23% | 103.79 | 88.88 | -11.92% |
| 8 | 239.27 ± 8.83 | 268.89 ± 1.48 | +8.10% | 158.27 | 128.46 | -16.96% |
| 16 | 343.97 ± 13.85 | 393.51 ± 3.31 | +9.07% | 287.17 | 201.52 | -23.27% |
| 32 | 443.86 ± 19.79 | 495.67 ± 3.40 | +7.55% | 491.63 | 455.09 | -1.54% |
| 64 | 562.66 ± 27.45 | 635.53 ± 2.23 | +9.16% | 932.23 | 837.05 | -3.61% |

Throughput is generated audio duration × 12.5 codec frames/s divided by cohort
wall time; higher is better. Throughput columns show mean ± sample SD across
three trials per arm. TTFA is time to first audio; lower is better. Each p95
column shows the **mean of three per-trial p95s**, not a pooled request p95.
Strict throughput gain is `min(candidate throughput) / max(reference throughput) - 1`;
conservative p95 change is `max(candidate p95) / min(reference p95) - 1`.
These conservative ratios are not ratios of the displayed means. All seven
cohorts passed the frozen gates: throughput ratio > 1.05, p95 ratio <= 1.05.

Both arms used the same single card, BF16 model, environment and workload:

- Model: `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`, revision
  `0c0e3051f131929182e2c023b9537f8b1c68adfe`; mono 24 kHz PCM16 output.
- Reference: [InferMatrixLab/qwen3-tts-engine](https://github.com/InferMatrixLab/qwen3-tts-engine/tree/b4451682abac651f26046f8d27467de3f007e1e7)
  at `b4451682abac651f26046f8d27467de3f007e1e7`, using the saved optimized command.
- Measured C++ candidate: `547270db4d41602f868dddb0f8c406858c17d29c`;
  [source/binary manifest and exact command](evidence/c005-rotary-tiling/plan/formal-plan.json).
  Opt-in `--predictor-rope paired --rotary-head-tile auto --audio-delivery inline`,
  with `--prewarm-decode`, max batch 64, codec batch 4 and chunk 8. Conservative
  defaults are not the configuration measured in this table.
- Runtime: Python 3.12.13, PyTorch 2.10.0, torch_npu 2.10.0.post4,
  CANN 9.1.0, qwen-tts 0.1.1, transformers 4.57.3; full package/library hashes
  and environment variables are retained in the manifest.
- Workload: 128 fixed texts (64 English/Ryan + 64 Chinese/Vivian), seed 42,
  `max_new_tokens=2048`; SHA256
  `5007716c83b29d0247b2c6291b9704c652e01a94362c19e90ea3cb34987060c7`.
  Three alternating pairs (AB/BA/AB), 128 timed requests per arm/cohort;
  readiness, graph capture and `max(2, concurrency)` warmup requests excluded.

All **5,376 timed requests** reached real stop/EOS; all **2,688 paired PCM
outputs were exact**, and all six servers and 42 benchmark processes exited 0.
See [the reproducible assessment](evidence/c005-rotary-tiling/results/formal/assessment.json),
[per-request results and lifecycles](evidence/c005-rotary-tiling/results/formal/),
[evidence/archive retrieval guide](evidence/c005-rotary-tiling/plan/README.md)
and [reviewed benchmark PR #11](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/11).
The total gain compares the engines; tiling alone contributed only about
1.1–1.4% throughput in the separate high-concurrency native control.

**Scope and known limitations:** PASS applies to this fixed corpus/configuration.
Exact PCM establishes relative equivalence here, not independent speech quality
or production reliability. The expanded C007 corpus found an intermittent
shutdown failure and eight nonexact C16 outputs; [PR #15](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/15)
remains blocked, and later exact runs do not prove a fix. Independent quality
qualification and final independent/owner acceptance remain open. The execution
core is C++; Python still performs model loading, tokenization and graph capture.
These HTTP results do not measure CLI streaming latency.

Every iteration starts with its own RFC design before a PR. Except for init PR
#1, merging requires actual A2 validation and an itemized review comment on the
PR. See the [mandatory review checklist](docs/pr-review-checklist.md).

The C++ core owns active requests, frame advancement, decode graph replay, codec
replay, slot compaction and PCM conversion. Python loads official weights,
tokenizes prompts, prepares prefill and captures NPU graphs. The original
`ContinuousModel.tick` is not called by the native runtime. The HTTP adapter
reuses the pinned reference service protocol. This is a mixed-bootstrap C++
runtime, not a Python-free model loader or a general model framework.

Prerequisites: Linux/aarch64, PyTorch 2.10, torch_npu 2.10.0.post4, CANN 9.1,
qwen-tts 0.1.1, transformers 4.57.3, Triton Ascend, a C++17 compiler and CMake.
Use a separate virtual environment. A pinned reference checkout is required for
model adapters and graph construction; it must be
`InferMatrixLab/qwen3-tts-engine@b4451682abac651f26046f8d27467de3f007e1e7`.
Those reused files are Apache-2.0 and retain their original attribution.

The source pin is checked at startup, including tracked and untracked changes.
Install model dependencies in an isolated environment. Preserve the CANN
`PYTHONPATH` supplied by the development image. The currently used image contains
an incompatible optional `kernels` installation; it was removed only inside the
dedicated campaign container, not the shared development container.

```bash
cmake -S /work/engine -B /work/build \
  -DPython3_EXECUTABLE=/work/venv/bin/python -DCMAKE_BUILD_TYPE=Release
cmake --build /work/build -j 2
export OMP_NUM_THREADS=4 HF_HUB_OFFLINE=1
export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2
export PYTHONPATH=/work/reference:$PYTHONPATH

# Native executable: Python loads weights/admissions and captures new shapes;
# the C++ main loop directly replays the graphs and writes complete WAV files.
/work/build/qtts --reference-root /work/reference --model /model \
  --workload /work/reference/evidence/campaign-20261017/plan/workload-128.jsonl \
  --slots 4 --requests 4 --predictor-rope paired --rotary-head-tile auto \
  --output /work/cli-development-probe

# The protocol-compatible HTTP entrypoint uses the same native C++ core.
/work/venv/bin/python /work/engine/serve.py \
  --reference-root /work/reference --native-build /work/build --model /model \
  --max-batch-size 64 --prewarm-decode --port 8199 \
  --predictor-rope paired --rotary-head-tile auto --audio-delivery inline
```

The paths above describe the isolated A2 container, not arbitrary host defaults.
Check the selected physical device is available before launching. Set device
visibility outside the process; logical `npu:0` means the selected visible device.
Initial Triton compilation and graph capture can take several minutes. Health
readiness and workload warmup must finish before timed measurements.

Run the compiled ownership tests without using an NPU:

```bash
PYTHONPATH=/work/build:$PYTHONPATH /work/venv/bin/python \
  /work/engine/test_native_state.py -v
```

`probe.py` compares complete English/Chinese generation, or adds
`--cancel-and-reuse` to exercise live compaction. Probe timings include capture
and are not benchmark results. `campaign.py` runs alternating reference/native
HTTP trials with owned-process cleanup and full retained audio. For the frozen
campaign use the default three repeat pairs, 128 requests and C1/2/4/8/16/32/64:

```bash
/work/venv/bin/python /work/engine/campaign.py \
  --reference-root /work/reference --native-build /work/build --model /model \
  --workload /work/reference/evidence/campaign-20261017/plan/workload-128.jsonl \
  --predictor-rope paired --rotary-head-tile auto --audio-delivery inline \
  --output /work/formal-001
/work/venv/bin/python /work/engine/assess.py \
  --run /work/formal-001 --output /work/formal-001/assessment.json
```

The assessment recomputes metrics from request records, hashes retained PCM and
checks actual benchmark/server exit codes. A reduced cohort cannot become a
formal PASS. Different PCM leaves relative quality INCONCLUSIVE until independently
scored; a lower-level test cannot establish full audio quality. Formal evidence
must also retain the model hashes, environment, physical-device observations and
the exact binary/source identities. Upstream 910B1 numbers are not local A2 results.

All configuration is through CLI arguments; JSON outputs are measurement evidence
or request data, not a second configuration interface. The reference's frozen
command JSON is imported provenance, not a user configuration entrypoint.

## Iteration record

[rsi.py](rsi.py) integrates the pinned InferRSI RunSpec/runner library with
CLI `run`, `trial` and `validate` commands; see [R1](docs/iterations/r1.md).
Pass a clean exact SDK checkout with `--inferrsi-root`; `--dry-run` prints a plan
without certifying model/NPU readiness. Its primary-cohort report stays separate
from authoritative seven-cohort `tts-final.json`. A short exact-audio smoke
remains whole-target INCONCLUSIVE. C001-C005 used `campaign.py`; they were not
retroactively executed by InferRSI.

See [C001](docs/iterations/c001.md), [C002](docs/iterations/c002.md), and
[C003](docs/iterations/c003.md). The paired predictor rotary path is opt-in via
`--predictor-rope paired` on the HTTP/CLI/probe/campaign entrypoints; `native`
remains the default. C002's formal performance result was FAIL.
CPU evidence tests run with
`python -m unittest discover -s tests -v`; compiled ownership tests require the
A2-built extension and run separately with `test_native_state.py -v`.
