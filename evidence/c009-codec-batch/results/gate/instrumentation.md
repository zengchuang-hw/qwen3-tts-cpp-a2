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

The snapshots in `gate-batch8.json` close the question directly, without needing
that mapping at all:

| Snapshot of NPU 3 process list | Text | Card 3 HBM |
|---|---|---|
| before (t0) | `No running processes found in NPU 3` | 3419 MB |
| after readiness | `227061 ... 26383` | 29761 MB |
| after exit | `No running processes found in NPU 3` | 9601 MB |

So: the card had **no process at all** and 3419 MB before the gate started, the
server that appeared at readiness is host PID 227061 with 26383 MB (which is the
gate's own server; 29761 - 3419 = 26342, consistent with that process plus baseline),
and the card was free again after exit. 261554 is the same server's
container-namespace PID.

State after the iteration:

- both PID names from the gate are gone (`/proc/261554`, `/proc/227061` absent);
- our container has no live python or serve process (`ps -ef` inside shows only
  pre-existing `<defunct>` entries from earlier work);
- the only process on card 3 later that day is host PID 472631, user `townwish`,
  started 14:45:49, command `/home/townwish/workspace/.../python -u
  /tmp/bench_compare.py`, i.e. another user's job that started well after this
  iteration's campaigns ended at 13:16. It is recorded as neighbour occupancy for
  any later run, not as part of this evidence.

## 3. 9601 MB on card 3 after the server exited

Observation only, recorded in `README.md` without interpretation:

- it is not called a leak;
- it is not connected to #16/C008 (that RFC's teardown failure has its own
  diagnostics and none of this iteration's runs are used as evidence for it);
- at the time of that snapshot our server had exited with status 0, and no claim is
  made about which process owned the remaining device memory afterwards.
