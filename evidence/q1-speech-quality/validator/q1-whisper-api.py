"""Actual CPU decode API probe; retained old audio gets no Q1 quality acceptance."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, '/work/q1-attempt02/source')
from quality_core import ASR_NEW_TOKENS, PREFIX, sha256
from speech_scorer import read_pcm

import numpy as np
import torch
from scipy.signal import resample_poly
from transformers import WhisperProcessor, WhisperForConditionalGeneration

torch.set_num_threads(4)
torch.manual_seed(20261019)
root = Path('/work/quality-models/openai--whisper-small-973afd24965f')
expected = json.loads(Path('/work/q1-attempt02/source/data/q1-models.json').read_text())[0]
checked = {}
for row in expected['files']:
    if row['rfilename'] == 'pytorch_model.bin':
        continue
    path = root / row['rfilename']
    if path.stat().st_size != row['size']:
        raise ValueError('Whisper asset size differs')
    digest = sha256(path)
    if row['lfs']:
        if digest != row['lfs']['sha256']:
            raise ValueError('Whisper weight differs')
    else:
        data = path.read_bytes()
        if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != row['blobId']:
            raise ValueError('Whisper Git asset differs')
    checked[row['rfilename']] = digest
processor = WhisperProcessor.from_pretrained(root, local_files_only=True)
model, loading = WhisperForConditionalGeneration.from_pretrained(
    root, local_files_only=True, use_safetensors=True, output_loading_info=True, attn_implementation='eager')
if any(loading.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
    raise ValueError('incomplete pretrained weights: ' + str(loading))
model.to(device='cpu', dtype=torch.float32).eval()
path = Path('/work/c007/results/heldout/r1-reference/c4/00000.wav')
pcm = read_pcm(path)
samples = resample_poly(np.frombuffer(pcm, dtype='<i2').astype(np.float32) / np.float32(32768),
                       up=2, down=3, window=('kaiser', 5.0), padtype='constant').astype(np.float32)
prefix = [model.config.decoder_start_token_id] + [token for _, token in
    processor.get_decoder_prompt_ids(language='en', task='transcribe', no_timestamps=True)]
with torch.inference_mode():
    inputs = processor(samples, sampling_rate=16000, return_tensors='pt', return_attention_mask=True)
    output = model.generate(**inputs, decoder_input_ids=torch.tensor([prefix]), language='en',
        task='transcribe', return_timestamps=False, do_sample=False, num_beams=1,
        max_new_tokens=ASR_NEW_TOKENS, return_dict_in_generate=True, output_scores=False)
sequence = output.sequences[0].tolist()
if prefix != PREFIX['English'] or sequence[:4] != prefix or not 0 < len(sequence[4:]) < ASR_NEW_TOKENS or sequence[-1] != 50257:
    raise ValueError('actual Whisper full-token API differs: ' + str(sequence))
record = {'status': 'CPU_API_SUPPORTED', 'scope': 'decode contract only; old C007 output is NOT Q1 accepted generation',
          'device': str(next(model.parameters()).device), 'dtype': str(next(model.parameters()).dtype),
          'asset_sha256': checked, 'loading_info': loading, 'sequence': sequence, 'prefix': prefix,
          'transcript': processor.decode(sequence[4:], skip_special_tokens=True),
          'wav_sha256': sha256(path), 'script_sha256': sha256(Path(__file__))}
with Path('/work/q1-attempt02/whisper-api-probe.json').open('x') as stream:
    stream.write(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
