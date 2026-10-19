# R1 actual InferRSI adapter qualification

**PASS for adapter delivery.** The new short NPU experiment remains whole-target
**INCONCLUSIVE**, not a new formal performance result.
Prior [RFC #14](https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/14) and
comments are preserved here. Historical C001-C005 used `campaign.py`; neither
replay nor this merge retroactively makes them SDK-run experiments.

Final A2 tested T: `b628b2ac95b6c49a395cc792e5a770c7e9e1fdda`.
Assessed base: `9bddd4cb39ad902e3e6be0eeec4900277427494c` (Q1 tooling integrated).
`../patch/source-manifest-02.json` contains all 43 canonical Git file hashes.
The subsequent evidence commit changes no tested source. Actual Release binary
SHA256:

- extension: `a401f0a71ff5df0fb78c748299aa140095ae6c8ce2b5c70ad974d206a0ae5e00`.
- qtts: `d6f1559bc7f65e9a53efff6aef2a173a6e8452847a3b91cee737b5eb24c69154`.

## Exact dependencies and environment

InferRSI `bd5e356ac9267362c80f27adba61d76e047583c7`, clean Git/import paths;
baseline qwen3-tts-engine `b4451682abac651f26046f8d27467de3f007e1e7`;
TTS model `0c0e3051f131929182e2c023b9537f8b1c68adfe` and its 11 audited assets.
The SDK source is a shallow snapshot of that exact public commit, not a rewritten
commit. The first bundle import omitted its shallow boundary and failed before
tests; restoring the original boundary in a new directory made fetch, checkout
and fsck succeed. This failed preparation and correction remain in the control
logs. No upstream SDK or shared environment was changed.

`zhuangzeliang@8.92.7.131`, dedicated `zc-qwen3-tts-cpp-20261019`, image
`sha256:e78fc581345117b32007a0ba7c337e06ac71df8200bbe609142f294c18f42dc3`.
Physical 910B3 card3, logical npu:0. The final active driver witness maps host
PID2563233 to container/native lifecycle PID102590 and the exact source-git
serve.py argv. Before-run idle snapshots, raw driver/owned-container process
observations, package/system/model/source/binary identities and true command
exits are retained. Compiled ownership tests use CPU tensors on A2; the real
TTS smoke is separate NPU evidence. Known source clock-skew warnings stay visible.

## Actual commands and results

`../results/attempt-02/results/validation.json` records every actual argv, cwd,
exit, wall time and log hash. The preparation used the mandatory source sync,
then a credential-free Git bundle restored a clean exact source checkout at
`/work/r1-attempt02/source-git`; build/output live outside it. The tested source
and environment/model identities match before and after all checks.

- CPU25, fresh Release configure/build and compiled CPU ownership4: all exit0.
- Pinned SDK CPU subprocess fixtures: real AB/BA/AB order and source snapshots
  passed. Their 100/120 values are explicitly synthetic and are not TTS speed.
  A separate 3-second hard-timeout fixture actually exited -9, retained SDK
  INCONCLUSIVE, and left no live owned server/child (zombies are not running).
- `rsi.py run --dry-run`: exit0 plan only, not model readiness.
- Actual SDK run ID `20261019T094024Z-391a8d3649`, under
  `/work/r1-attempt02/results/runs/`. Paired/auto/inline, physical3, frozen original
  workload, C4 x4 requests x one pair, warmup4. Eight timed requests completed
  EOS/streams with four actual PCM-exact pairs. Both servers exited0, TERM sent,
  KILL not needed and remaining_pids empty. The SDK source integrity is verified.
- Baseline helper/group PID102246 owns server102252; candidate helper/group
  PID102584 owns server102590. Both have server_start_new_session=false and
  mode=inferrsi_trial_group. SDK cleanup and actual exits are in each lifecycle.
- The actual primary generic report is PASS; authoritative TTS and final results
  stay INCONCLUSIVE with formal_coverage=false. Validation-command exit0 proves
  its PCM/completeness scope; top-level adapter exit2 preserves missing full
  seven-concurrency/128-request/three-pair acceptance. This is the intended gate,
  not an ignored failure.

Final required command wall time summed to about 173 seconds, within the RFC's
20-minute adapter budget. Attempt01 on old base0e917/source dd3ed59 also passed
its CPU13/build/ownership/CPU-fixture/smoke/replay scope. After Q1 merged, the
whole required sequence was rerun against final T, including CPU25 and a new
unique actual SDK run; the old source result did not substitute for new-base
validation. Both attempts and their media remain separate.

## Immutable legacy replay

New assessor reads the original evidence without copying/aliasing trial media.
It preserves each cohort, performance, exact quality and coverage verdict:

| Existing experiment | Actual replay exit | Verdict | Original / replay SHA256 |
|---|---|---|---|
| C002 | 1 | FAIL | c884dbfc429c65272a41fde68101ef57c5fa8152e08985939d7c60e9f3ec3659 / e12034a613b1cf185a7045c2a8af8e7c5be4a2bc443c2062d2e50cddfea36e40 |
| C005 | 0 | PASS | 20caa94051bf8cca01e912ca541abc71ea6ca4bc52d07f7dc51a142b3e1b1570 / same |

C002's current provenance/description fields change the serialized hash, not the
compared outcomes; its original assessment is unchanged. These are actual A2
auditor replays, not fresh NPU speed measurements. Full legacy WAV/metadata
archives remain at the paths already recorded by those iterations.

## Scope, alternatives and retrieval

Use the library RunSpec API with truthful repo_type=qwen3_tts_cpp; the fixed
upstream CLI enum does not provide this target. Rejected alternatives were
pretending to be vLLM/Strata, modifying the upstream SDK in this iteration,
copying/aliasing WAVs into fabricated directories, or accepting one generic
primary metric as full TTS acceptance. The optional supervision branch leaves
standalone campaign behavior unchanged and keeps SDK workers in their actual
owned trial group. Unknown/missing evidence and short coverage cannot PASS.

No TTS core/kernel/default or new formal speed promotion is included. C005's
separate frozen performance result remains qualified in its original scope;
C007/PR15, C008 and final independent/owner project acceptance remain open.
README now gives the explicitly qualified paired/auto/inline command and its
broader limits. No package was published or production system activated.

`archive-manifest.json` lists original artifacts and retrieval paths. On A2 at
`/work/r1-evidence-20261019/`, host-mapped to
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/r1-evidence-20261019/`:

- metadata.tar: 1,269,760 bytes /375 files,
  SHA256 `3fab33eb58aff0dbdb6e90b0b4da09e9fab5cc16212bda14a569fb53c5176e33`.
- media.tar: 6,615,040 bytes /32 WAVs across two actual SDK experiments,
  SHA256 `330a403c1a350cbf19a5651bacdb775c5c967be633efc8f12568d16af5b12c34`.

Git retains all aggregate request/results/source/ownership/verdict records;
redundant five-digit request sidecars remain in the full raw metadata tar.
`../patch/validator-source-map.json` maps raw uploaded script bytes to canonical
Git LF bytes. No fresh run is invented to explain line-ending differences.
