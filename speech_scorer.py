"""Lazy CPU inference for the fixed Q1 models; never imports accelerator runtimes."""

import hashlib
import wave

from quality_core import (ASR_MAX, ASR_NEW_TOKENS, MODEL_REVISIONS, PROTOCOL,
                          SPEAKER_MAX, audit_score, windows)


def read_pcm(path):
    with wave.open(str(path), 'rb') as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 24000):
            raise ValueError('Q1 requires mono 24kHz PCM16 WAV')
        frames = audio.getnframes()
        pcm = audio.readframes(frames)
    if not pcm or len(pcm) != frames * 2:
        raise ValueError('empty or truncated WAV')
    return pcm


class SpeechScorer:
    def __init__(self, assets, lock_sha):
        import numpy as np
        import torch
        from scipy.signal import resample_poly
        from transformers import (Wav2Vec2FeatureExtractor, WavLMForXVector,
                                  WhisperForConditionalGeneration, WhisperProcessor)

        self.np, self.torch, self.resample = np, torch, resample_poly
        self.lock_sha = lock_sha
        torch.set_num_threads(4)
        torch.manual_seed(20261019)
        paths = {row['model']: row['path'] for row in assets}
        self.processor = WhisperProcessor.from_pretrained(paths['openai/whisper-small'],
                                                          local_files_only=True)
        self.extractor = Wav2Vec2FeatureExtractor.from_pretrained(
            paths['microsoft/wavlm-base-plus-sv'], local_files_only=True)
        self.asr, asr_info = WhisperForConditionalGeneration.from_pretrained(
            paths['openai/whisper-small'], local_files_only=True, use_safetensors=True,
            output_loading_info=True, attn_implementation='eager')
        self.speaker, speaker_info = WavLMForXVector.from_pretrained(
            paths['microsoft/wavlm-base-plus-sv'], local_files_only=True, use_safetensors=False,
            weights_only=True, output_loading_info=True, attn_implementation='eager')
        self.loading = {'asr': asr_info, 'speaker': speaker_info}
        for info in self.loading.values():
            if any(info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
                raise ValueError('model loading did not use the complete pretrained state: ' + str(info))
        for model in (self.asr, self.speaker):
            model.to(device='cpu', dtype=torch.float32).eval()
            if any(p.device.type != 'cpu' or p.dtype != torch.float32 for p in model.parameters()):
                raise ValueError('Q1 model parameters must be CPU float32')
        if self.asr.config.max_target_positions != 448:
            raise ValueError('Whisper decoder capacity changed')
        self.identity = {'classes': [type(self.asr).__name__, type(self.speaker).__name__],
                         'device': 'cpu', 'dtype': 'float32', 'threads': torch.get_num_threads(),
                         'seed': 20261019, 'loading_info': self.loading,
                         'attention': 'eager', 'remote_code': False}
        self.cache = {}

    def score(self, path, language):
        pcm = read_pcm(path)
        digest = hashlib.sha256(pcm).hexdigest()
        key = (digest, language)
        if key in self.cache:
            return self.cache[key]
        np, torch = self.np, self.torch
        wave24 = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / np.float32(32768)
        samples = self.resample(wave24, up=2, down=3, window=('kaiser', 5.0),
                                padtype='constant').astype(np.float32)
        if not np.isfinite(samples).all() or not len(samples):
            raise ValueError('resampled audio is not finite/nonempty')
        record = {'status': 'SCORED', 'protocol': PROTOCOL, 'models': MODEL_REVISIONS,
                  'lock_sha256': self.lock_sha, 'pcm_sha256': digest, 'pcm_bytes': len(pcm),
                  'samples_16k': len(samples), 'language': language, 'asr': [], 'speaker': []}
        lang = {'English': 'en', 'Chinese': 'zh'}[language]
        prefix = [self.asr.config.decoder_start_token_id] + [token for _, token in
                  self.processor.get_decoder_prompt_ids(language=lang, task='transcribe', no_timestamps=True)]
        if len(prefix) != 4:
            raise ValueError('expected four fixed Whisper prefix tokens')
        with torch.inference_mode():
            for start, end in windows(len(samples), ASR_MAX):
                inputs = self.processor(samples[start:end], sampling_rate=16000,
                                        return_tensors='pt', return_attention_mask=True)
                sequence = self.asr.generate(
                    **inputs, decoder_input_ids=torch.tensor([prefix]), language=lang, task='transcribe',
                    return_timestamps=False, do_sample=False, num_beams=1,
                    max_new_tokens=ASR_NEW_TOKENS, return_dict_in_generate=True,
                    output_scores=False).sequences[0].tolist()
                if sequence[:4] != prefix:
                    raise ValueError('Whisper language/task prefix changed')
                generated = sequence[4:]
                record['asr'].append({'start': start, 'end': end, 'prefix': prefix,
                                      'generated_tokens': generated,
                                      'eos_token_id': self.asr.config.eos_token_id,
                                      'transcript': self.processor.decode(generated, skip_special_tokens=True)})
            for start, end in windows(len(samples), SPEAKER_MAX):
                segment = samples[start:end]
                real = len(segment)
                inputs = self.extractor(segment, sampling_rate=16000, return_tensors='pt',
                                        return_attention_mask=True)
                if real < 16000:
                    # Normalize actual samples before padding; padded samples have mask 0.
                    inputs['input_values'] = torch.nn.functional.pad(inputs['input_values'], (0, 16000 - real))
                    inputs['attention_mask'] = torch.nn.functional.pad(inputs['attention_mask'], (0, 16000 - real))
                feature_count = int(self.speaker._get_feat_extract_output_lengths(torch.tensor(real)))
                # WavLM's TDNN needs positive output through every dilated kernel.
                for kernel, dilation in zip(self.speaker.config.tdnn_kernel, self.speaker.config.tdnn_dilation):
                    feature_count -= dilation * (kernel - 1)
                if feature_count < 1:
                    raise ValueError('insufficient real speaker feature context')
                embedding = self.speaker(**inputs).embeddings[0].tolist()
                record['speaker'].append({'start': start, 'end': end,
                                          'real_samples': real, 'embedding': embedding})
        # Retain real model outputs even when strict completeness rejects them.
        try:
            audit_score(record, digest, language, self.lock_sha)
        except (ValueError, KeyError, TypeError) as error:
            record.update(status='INCONCLUSIVE', error=f'{type(error).__name__}: {error}')
        self.cache[key] = record
        return record
