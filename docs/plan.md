# Qwen3-TTS C++ / Ascend A2 campaign

Status: implementation in progress; performance and full quality INCONCLUSIVE.
Date: 2026-10-19 (Asia/Shanghai).

## Contract

Build an actual C++ execution core for Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
and improve end-to-end streaming performance against the independent
InferMatrixLab/qwen3-tts-engine, on the same physical Ascend A2 device.
The control package stays independent of torch and accelerator runtimes.

Baseline source: `https://github.com/InferMatrixLab/qwen3-tts-engine`,
`b4451682abac651f26046f8d27467de3f007e1e7`; published performance instead
describes `e783a64b0fb4f9ade2ffb3980b3e1f74a00c9a6a` on 910B1. Those numbers
are imported evidence, not this campaign's 910B3 baseline.
InferRSI measurement source: `bd5e356ac9267362c80f27adba61d76e047583c7`.
Strata reference: `477ac13cbe8e582c20484871ce459d20d82df09d`; borrow graph,
buffer lifetime and state ownership ideas, not MoE placement or CUDA results.

## Implementation and acceptance

1. Inspect devices, model assets and compiler/runtime availability without
   disturbing other jobs. Use a dedicated source tree and development environment.
2. Reproduce the optimized frozen Python baseline on a free physical device.
3. Implement C++ execution/state code and a build/run entrypoint. Clearly record
   any Python bootstrap, graph construction and official model dependencies.
   A C++ launcher forwarding the original Python inference loop is insufficient.
4. Validate operators and state, then complete real English/Chinese generation,
   EOS, long/short requests, cancellation, interleaving and slot reuse.
5. Profile outside timed runs; change one mechanism per candidate. Freeze source,
   build flags, dependency identities and binary SHA256 before formal comparisons.
6. Use identical BF16 weights, prompt corpus, voices, sampling, output limits,
   streaming format and hardware. Measure successful full requests, audio-duration
   throughput, TTFA p50/p95 and RTF at C1/2/4/8/16/32/64. Do not count truncation
   or failures as speedups. At least three alternating AB/BA repeat pairs.
7. Desired performance gate: greater than 5% throughput improvement at each
   qualified concurrency, with no greater than 5% TTFA p95 regression; report
   every concurrency separately. These thresholds must not be relaxed after runs.
8. Prefer byte-identical audio for semantics-preserving changes. If output changes,
   run independently pinned ASR and speaker scoring: WER/CER no more than +1
   percentage point and speaker cosine no more than -0.02 versus the best measured
   baseline per metric/concurrency, plus request/audio integrity. No quality PASS
   from build tests or upstream reports. Record any missing scorer as INCONCLUSIVE.

Build, correctness, performance and delivery have separate PASS/FAIL/INCONCLUSIVE
outcomes. A compiled prototype does not satisfy the performance objective.
The owner authorized a dedicated private repository and iteration PR merges on
2026-10-19. Each PR records its actual qualification; merging a research result
does not assert a performance PASS. Package publication and production activation
are outside the campaign.

## Environment observations

The configured host is `zhuangzeliang@8.92.7.131`. Initial inspection found eight
healthy 910B3 devices; 0, 1 and 5 carry unrelated vLLM processes. Device 2 had no
listed process and is the initial single-card candidate; check again before use.
The standard `zc-vllm-omni-dev` container currently differs from the historical
skill image: torch 2.10.0+cpu, torch_npu 2.10.0.post4, CANN 9.1.0,
transformers 5.14.1. Do not overwrite its dependencies. The user's cached model
is `/home/zhuangzeliang/models/Qwen3-TTS-12Hz-1.7B-CustomVoice`.
