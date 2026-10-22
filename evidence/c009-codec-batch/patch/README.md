# Patch — intentionally empty

C009 changed no runtime code. This iteration is a configuration-plumbing and
measurement delivery, so there is no kernel, graph, capture or scheduling patch to
record here.

## What the commit does change

- `campaign.py`: new `--codec-batch-size` (default 4, bounded `[1,8]`), appended to the
  shared `serve.py` construction used by both arms of a native-engine campaign.
- `probe.py`: native arm threads the value through; the pinned upstream reference arm
  keeps 4 and rejects other values with a parser error.
- `tests/test_evidence_contracts.py`: four CPU contracts for the above.

Unchanged, and verified as such by tts-SE against the branch head: `serve.py`,
`graph_model.py`, `native/runtime.cpp`, `native/main.cpp`, `native/runtime_api.h`,
`assess.py`.

## How to inspect the real diff

```
git diff origin/main...codex/c009-codec-batch -- campaign.py probe.py tests/test_evidence_contracts.py
```
