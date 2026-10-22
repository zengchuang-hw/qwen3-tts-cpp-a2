# C009 readiness gate — batch 8 (non-timed)

One standalone `serve.py` start at codec batch 8, measured to readiness, then
stopped. Non-timed diagnosis; this file carries no throughput conclusion.

## Reading

- Readiness: **543.341 s** against the frozen 720 s budget (within budget).
- `_capture_codecs`: **508.018 s** at batch 8 (64 graphs).
- Server exit: **0**; one `SIGINT`, no `SIGKILL`.
- Card 3 HBM at readiness: **29761 MB**, from a **3419 MB** baseline
  (+26342 MB for the server, capture and prewarm).
- Card 3 AICore stayed 0% while idle-waiting; temperature 43-47 C.
- Raw record: `gate-batch8.json` (argv, environment, npu-smi before / after
  readiness / after, pid, log path). Server log: `gate-batch8.log`.

## Missing measurement, stated rather than estimated

`torch.npu.max_memory_allocated()` was not instrumented in this run: the timing
wrapper logged only the capture wall clock. The device-side HBM figure above is a
real measurement; the torch-side allocator peak is recorded as **not collected**
and is not filled in from reasoning.

## What this implies for the budget

Four server starts are needed for AB (two campaigns x two arms). Capture alone is
8.5 min per batch-8 start, so AB cannot complete inside the 30-minute BA
condition; BA is therefore not attempted and results record "AB only, no order
control". The 45-minute iteration budget is measured from 12:55:41; if AB runs
past it, the overrun is recorded as such rather than hidden by dropping cohorts.
