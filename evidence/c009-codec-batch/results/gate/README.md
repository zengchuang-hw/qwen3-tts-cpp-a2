# C009 readiness gate — batch 8 (non-timed)

One standalone `serve.py` start at codec batch 8, measured to readiness, then
stopped. Non-timed diagnosis; this file carries no throughput conclusion.

## Reading

- Readiness: **543.341 s** against the frozen 720 s budget (9.05 min, within budget).
- `_capture_codecs`: **508.018 s** at batch 8 (64 graphs).
- Server exit: **0**; one `SIGINT`, no `SIGKILL`.
- Card 3 AICore stayed 0% while idle-waiting; temperature 43-47 C.

## Memory: measurement points and wording

The three snapshots are all card 3 (`0000:82:00.0`) device-side HBM as reported by
`npu-smi`, taken at these points:

| Snapshot | When | Card 3 HBM |
|---|---|---|
| before | immediately before the server process was launched (t0) | 3419 MB |
| after_ready | immediately after `/health` returned `ready`, server **still running** (t0 + 543.341 s) | 29761 MB |
| after | after the server exited (SIGINT, exit 0) | 9601 MB |

Wording that applies: these are **device-side allocated HBM** figures. They are not
a `torch.npu` allocator peak and must not be described as one. The 29761 MB reading
is taken while the server is alive and ready, so it is a live footprint at
readiness, not a post-exit residue; the 9601 MB reading after exit is recorded as an
observation only (device-side, after the process was gone) and is not used as a
peak.

## Promised but not collected this round

`plan/README.md` gate 5 asked for `torch.npu.max_memory_allocated()` before and
after capture. That figure **was not collected in this round**: the timing wrapper
logged only the capture wall clock. It is recorded as not collected, not estimated
and not back-filled. The device-side HBM series above is the substitute evidence,
under the wording restriction stated above.

Process lesson carried into the next iteration: instrument allocator peak sampling
*before* starting the capture run, rather than adding it afterwards.

## Budget: what this reading did and did not predict

This 508.018 s capture is a **cold first-run** figure that includes Triton
compilation. Measured campaign starts were much shorter: codec4 took 3 min 48 s and
codec8 4 min 16 s, so AB finished inside the 45-minute budget. An earlier draft
here predicted a structural overrun from this number; that prediction is withdrawn
as measured wrong and kept visible rather than deleted (see `../README.md`). The
order-control (BA) pair was not started because the exactness gate failed first,
not because of the budget. Improvement for the next iteration: give `campaign.py`
an arm-selection switch such as `--arms native` so a pilot does not pay for an arm
it will discard.
