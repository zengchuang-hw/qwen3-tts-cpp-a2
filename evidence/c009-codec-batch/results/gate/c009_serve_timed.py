"""Timing wrapper actually used for the C009 readiness gate (verbatim copy).

Kept as evidence because the gate record's argv points at this file rather than at
source/serve.py. It changes no runtime behaviour: it imports serve, times
NativeModel._capture_codecs, prints one line, and then hands control to serve.main()
with the original arguments.
"""

import sys
import time

sys.path.insert(0, "/work/c009/build")
sys.path.insert(0, "/work/reference")
sys.path.insert(0, "/work/c009/source")
import graph_model  # noqa: E402  (path setup must happen first)

_orig = graph_model.NativeModel._capture_codecs


def timed(self, codec_batch_size):
    start = time.perf_counter()
    try:
        return _orig(self, codec_batch_size)
    finally:
        print(
            "C009_CAPTURE seconds=%.3f batch=%d" % (time.perf_counter() - start, codec_batch_size),
            flush=True,
        )


graph_model.NativeModel._capture_codecs = timed
sys.argv = ["serve"] + sys.argv[1:]
import serve  # noqa: E402

serve.main()
