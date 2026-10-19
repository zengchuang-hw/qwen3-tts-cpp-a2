# Qwen3-TTS C++ / Ascend A2

Research engine for `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` on Ascend A2.
Implementation and measured iterations arrive through pull requests. Build,
correctness, quality and performance are reported separately as PASS, FAIL or
INCONCLUSIVE. An iteration may be merged as a documented research result without
meeting the overall performance objective.

The target is over 5% end-to-end throughput improvement at C1/2/4/8/16/32/64,
without more than 5% TTFA p95 regression, against the pinned optimized
`InferMatrixLab/qwen3-tts-engine` on the same device, weights and workload.

Every optimization PR records its mechanism, alternatives, source identities,
validation commands/results and limitations. CPU CI does not establish NPU speed.
No package publication or production activation is implied by a merge.
