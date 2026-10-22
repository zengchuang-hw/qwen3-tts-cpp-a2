# Gate instrumentation, PID namespaces and the post-exit HBM reading

Three questions raised in review, answered from evidence rather than from memory.

## 1. The gate ran a wrapper, not `source/serve.py`

Source: `c009_serve_timed.py` (beside this file, verbatim).

- What it does: inserts the build/reference/source paths, imports `graph_model`,
  replaces `NativeModel._capture_codecs` with a version that prints one
  `C009_CAPTURE seconds=<float> batch=<int>` line, then calls `serve.main()` with
  `sys.argv` set to `["serve", *original_args]`.
- What it does not do: no repository file was modified, no runtime path was
  replaced, no batching or sampling logic is touched, and `serve.main()` runs
  unchanged. The wrapper exists only to timestamp the capture call.
- Ready criterion: the gate polled `GET /health` and accepted only a JSON body whose
  `status` equals `ready`. That is the same condition `campaign.py` uses when it
  waits for a server (its readiness loop breaks on `health.get("status") == "ready"`),
  and the same endpoint `serve.py` exposes. There is no second definition of ready.
- Consequence for the record: `gate-batch8.json` `argv` naturally shows the wrapper
  path. The process it started is the same `serve.main()` a campaign would start,
  with the same serve flags; the wrapper adds one stderr line.

## 2. PID mismatch (gate 261554 versus npu-smi 227061)

The gate script ran inside the container, so `subprocess.Popen(...).pid` is a
**container-namespace** PID. `npu-smi` reports **host-namespace** PIDs. The two
namespaces are not a constant offset, which was verified with a throwaway process:

```
container-visible: 277704 sleep 240
host-visible     : 520432 sleep 240     (docker top)
container init 1 -> host 1004067        (docker inspect .State.Pid)
```

So the numeric difference between 261554 and 227061 is expected from the namespace
boundary alone; it is not by itself evidence that another process held the device.

State now (checked after the iteration finished):

- both PIDs from the gate are gone (`/proc/261554`, `/proc/227061` absent);
- our container has no live python or serve process (`ps -ef` inside shows only
  pre-existing `<defunct>` entries from earlier work);
- the only process on card 3 today is host PID 472631, user `townwish`, started
  14:45:49, command `/home/townwish/workspace/.../python -u /tmp/bench_compare.py`,
  i.e. another user's job outside this container, started well after this
  iteration's campaigns ended at 13:16.

Recorded as a fact: the mapping for the gate process cannot be recovered now that
both processes have exited; what is recoverable is the namespace explanation and the
current ownership of the card.

## 3. 9601 MB on card 3 after the server exited

Observation only, recorded in `README.md` without interpretation:

- it is not called a leak;
- it is not connected to #16/C008 (that RFC's teardown failure has its own
  diagnostics and none of this iteration's runs are used as evidence for it);
- at the time of that snapshot our server had exited with status 0, and no claim is
  made about which process owned the remaining device memory afterwards.
