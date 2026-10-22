# C009 results

Source/binary identity for both campaigns is in `codec4/identity.json` and
`codec8/identity.json`; environment in `codec4/environment-identity.json` and
`codec8/environment-identity.json`. Recompute any value with the commands in
`stamps.txt` (value, producing command and raw output on adjacent lines).

## Outcome: the exactness gate stops this iteration

Both campaigns exited 0 and every request completed with a real stop. The audio is
**not byte-identical** between codec batch 4 and codec batch 8, so RFC #22 gate 3
("any difference is FAIL") is what decides this iteration.

Per cohort, matched requests out of 128, and the stop count on both sides:

| Arm (delivery) | C16 | C32 | C64 | stops (4 / 8) |
|---|---:|---:|---:|---|
| r1-native (inline) | 105 / 128 | 58 / 128 | 12 / 128 | 128 / 128 |
| r1-reference (buffered) | 105 / 128 | 58 / 128 | 12 / 128 | 128 / 128 |

- The WAV-file SHA256 comparison gives exactly the same matched counts as the
  `pcm_sha256` comparison, so the difference is in the retained files, not only in
  a derived field.
- `codec_frames` matched **128 / 128 in every cohort for both arms**: generated
  audio length is unchanged, while PCM samples differ.
- Falsified hypothesis: RFC #22 assumed codec batch 4 -> 8 changes no audio
  mathematics. Under this source/binary/model/workload it changed somewhere between
  23 and 116 of 128 PCM streams per cohort, more as concurrency rises.

## Throughput: raw values only, no promotion

Recomputed from per-request `audio_seconds` and the cohort wall time
(`sum(audio_seconds) * 12.5 / wall_seconds`), ratio = value(8) / value(4):

| Cohort | inline ratio | buffered ratio |
|---|---:|---:|
| C16 | 0.989468 | 0.951727 |
| C32 | 1.016819 | 0.977404 |
| C64 | 1.052858 | 1.018306 |

The recomputed throughput agreed with the reported `throughput_frames_s` for all
twelve cohort/arm cells (`defects: []` in `comparison.json`).

Gate 3 precedes gate 4, so these ratios decide nothing here: this run is FAIL on
audio identity, not a threshold verdict, and no formal seven-cohort promotion is
proposed. They are recorded because the RFC asked for all adverse results to be
kept.

## n=1 rule, applied honestly

Had gate 3 held, the frozen table would have placed the inline C16 ratio in the
unresolved band and C64 above the upper band. Because the exactness gate failed
first, no band verdict is issued and nothing is described as separating the two
configurations.

## Arm selection and the secondary consistency check

Only the `r1-native` arm is a comparison basis (ruling 3a); the buffered arm exists
to discharge addition 2. Both arms show identical matched counts, so the inline arm
is not hiding a difference the buffered arm would expose - the difference tracks
the codec-batch setting both arms share, and no delivery-mode artefact is claimed.

## BA not run

RFC #22 gate 3 says any difference is FAIL and stops the follow-on work, so the
order-control (BA) pair was not started. This is a gate decision, not a budget
choice.

## Budget: measured

| Stage | Window (UTC) | Elapsed |
|---|---|---|
| codec4 campaign | 05:08:08 -> 05:11:56 | 3 min 48 s |
| codec8 campaign | 05:12:12 -> 05:16:28 | 4 min 16 s |

Both campaigns together took 8 min 04 s, inside the 45-minute budget measured from
12:55:41. Correction to an earlier draft note: the gate's 508.018 s capture is the
**cold first-run** figure (Triton compilation included); campaign starts were far
shorter, so the earlier "structural overrun" prediction is withdrawn as measured
wrong and is kept here rather than deleted.

## Non-default codec batch is not shown to be audio-equivalent

C009 measured different PCM at codec batch 8 versus the default 4 under an otherwise
identical configuration. Therefore: **a non-default codec batch is not proven to
produce byte-identical audio**, and the runtime default stays 4. Any later proposal
that raises it must first re-establish byte identity, or run the independent quality
route frozen for that iteration.

## Cold versus warm capture (recorded for the attribution iteration)

`gate-batch8.json` reports a 508.018 s capture, which is a **cold first-run** figure
including Triton compilation. The warm campaign starts were much shorter: the codec8
campaign (two arms, 64 graphs captured) took 4 min 16 s end to end, so per-arm model
load plus capture is of the order of a minute (range reference only, derived from
first/last cohort `results.json` mtimes rather than from an instrumented timer). The
nature of this pair is *consistent with* the cold-start explanation, not proof of it;
it is handed to #28 / C015 as the cheapest available corroboration.

## Neighbour occupancy

The gate snapshots show NPU 3 with no running process and 3419 MB before the start,
and no running process again after exit. A later neighbour job (`townwish`,
`/tmp/bench_compare.py`) occupies card 3 from 14:45:49; it started after this
iteration's campaigns ended at 13:16 and is not part of this evidence.

## Recompute

```
# branch head
git rev-parse refs/heads/codex/c009-codec-batch
# per-cohort records
sha256sum /work/c009/results/codec4/r1-native/c16/results.json   # cwd: /work/c009
# rebuild the comparison
cd /work/c009 && /work/venv/bin/python scripts/c009_compare.py   # writes results/comparison.json
```

WAV files stay on the A2 host under
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/c009/results/<tag>/<arm>/c<cohort>/`
(excluded from the repository to keep it small); every file's `pcm_sha256` is in
the corresponding `results.json`.
