# Process RFC #4: A2 validation

Design issue: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/issues/4
Delivery PR: https://github.com/zengchuang-hw/qwen3-tts-cpp-a2/pull/5

RFC created at 2026-10-19T04:04:50Z; PR created at 04:07:45Z, both GitHub
timestamps. Tested content: `6119f1ae52f9d296fdf211cf6b7152a6d2d03fcc` and
the actual 63-file synchronized snapshot in `source-manifest.json`.

Scope is process/documentation only. The iteration changes AGENTS, README,
the PR template and the review checklist. It does not change runtime, kernel,
model, scheduling, benchmark commands or validation thresholds. No new native
binary is needed and no speech/NPU performance claim is made.

Source was synced using the a2-run-tests `sync-to-a2.sh` script. The successful
sync marker is `sync-info.txt`; before/after tracked-source SHA256 aggregates
are equal in `../results/result.json`. The actual validator is archived at
`../validator/runner.py`. It ran inside `zc-qwen3-tts-cpp-20261019` on the A2
host; it ran the CPU suite and syntax checks and checked five local Markdown
links in the four changed documents. All commands and the runner exited 0.
The CPU suite passed all three tests. Device observations are retained for
environment context; no NPU inference was started or used as validation.

Original source/results location:
`/home/zhuangzeliang/zc/qwen3-tts-cpp-20261019/policy-review-6119f1a`.

Reproduce after syncing this tested snapshot and manifest to that location:

```bash
docker exec zc-qwen3-tts-cpp-20261019 /work/venv/bin/python \
  /work/policy-review-6119f1a/runner.py
```

The runner refuses to overwrite an existing results directory. Use a new,
explicitly named validation directory and update the archived runner's root
for a fresh reproduction; retain the old evidence unchanged.

The evidence-only follow-up commit is not a second A2 execution. Its diff and
continued applicability to final PR head/base must be checked in the required
PR review comment. Raw logs retain their original bytes and SHA256.
