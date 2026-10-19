# Qwen3-TTS native graph runtime for Ascend

Research implementation. See [the frozen plan](docs/plan.md).
Build, complete speech correctness and end-to-end performance must be qualified
separately; no speed claim is made by this README.

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
  --slots 4 --requests 4 --output /work/cli-development-probe

# The protocol-compatible HTTP entrypoint uses the same native C++ core.
/work/venv/bin/python /work/engine/serve.py \
  --reference-root /work/reference --native-build /work/build --model /model \
  --max-batch-size 64 --prewarm-decode --port 8199
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

See [C001](docs/iterations/c001.md). CPU evidence tests run with
`python -m unittest discover -s tests -v`; compiled ownership tests require the
A2-built extension and run separately with `test_native_state.py -v`.
