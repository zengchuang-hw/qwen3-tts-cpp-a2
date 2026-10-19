"""CPU compatibility score on retained audio, explicitly NOT retrospective acceptance."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, '/work/q1-attempt02/source')
from quality_core import sha256
from speech_quality import checked_lock, current_identity
from speech_scorer import SpeechScorer

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--freeze', type=Path, required=True)
p.add_argument('--wav', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
lock = checked_lock(args.freeze)
scorer = SpeechScorer(lock['identity']['assets'], sha256(args.freeze))
result = scorer.score(args.wav, 'English')
if current_identity(lock) != lock['identity']:
    raise ValueError('frozen source/assets changed during compatibility check')
record = {'status': 'CPU_INFERENCE_COMPLETED', 'scope': 'Q1 loading/preprocessing/decode compatibility only; '
          'old C007 audio is not prelocked generation and receives NO acceptance',
          'wav': str(args.wav), 'wav_sha256': sha256(args.wav),
          'scorer_identity': scorer.identity, 'score': result}
with args.output.open('x') as stream:
    stream.write(json.dumps(record, indent=2) + '\n')
print(json.dumps({'status': record['status'], 'scope': record['scope']}), flush=True)

