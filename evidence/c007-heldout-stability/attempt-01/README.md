# C007 attempt01: FAIL / blocked

Prior RFC13, PR15. Tested8fdc09973ca33c74a4918955397b24a0ecf0d13f;
engine inherited C005 unchanged. A2 CPU12, fresh build and ownership4 passed.
Held-out HTTP C4/C16 each32 per arm generated all128 complete stop requests,
but native server did not terminate within the original60 seconds and was
SIGKILLed: actual exit-9; reference exit0. Campaign actual exit1. This is FAIL,
not successful lifecycle validation. Stress was NOT RUN after this failure.

Post-failure actual-byte diagnosis: C4 PCM32/32 exact; C16 PCM24/32 exact.
Eight C16 outputs have identical frame counts but different sample values;
audio-only-diagnostic.json preserves indices, first divergence and amplitude
counts. Perceptual/ASR/speaker quality is NOT SCORED, never inferred from these
small numerical differences. Current exact-audio acceptance is not met.

Raw archives are immutable and listed in archive-manifest.json;168 WAVs include
40 warmups. Git retains full aggregate request records; redundant individual
sidecars stay in raw metadata archive. Source/binary/logs/true exits preserved.
No after-run environment PASS is invented after the early stop.

Root cause work follows prior RFC16. PR15 stays Draft; future source/protocol
changes require explicit mapping and a new run, without overwriting this one.
