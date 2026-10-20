"""Deterministic frame-based cancel/reuse stress; actual NPU process only."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
import wave
from serve import load_reference


def sha(data):
    return hashlib.sha256(data).hexdigest()


def create_model(args):
    if args.engine == 'native':
        from graph_model import NativeModel
        return NativeModel(str(args.model), 'npu:0', max_slots=16, prewarm_decode=True,
            predictor_rope=args.predictor_rope, rotary_head_tile=args.rotary_head_tile,
            audio_delivery=args.audio_delivery)
    from qwen3_tts_engine.continuous import ContinuousModel
    return ContinuousModel(str(args.model), 'npu:0', max_slots=16, pack_qkv=True,
        rms_norm='native', pack_mlp=True, fused_swiglu=True, native_gqa=True,
        text_only_rope=True, native_rope=True, native_rope_scope='predictor',
        triton_talker_rope=True, native_kv_update=True, triton_kv_update=True,
        incremental_codec=True, batch_prefill=True, graph_prefill=True,
        bucket_prefill=True, prewarm_prefill=True, direct_prompt=True,
        triton_snake=True, cache_codec_codebooks=True, codec_batch_size=4,
        triton_cdf=True, graph_embeddings=True, graph_sampling=True, prewarm_codec=True)


def structure(model):
    return {'capacity':model.arena.capacity,
        'prefills':sorted(map(str, model.prefills)),
        'talker_graphs':sorted(map(str, model.graphs)),
        'codec_graphs':sorted(map(str, getattr(model.codec,'graphs',{}))),
        'sampling_graphs':sorted(map(str, model.samplers)),
        'predictor_graphs':sorted(map(str, model.predictor.captures)),
        'native_decodes':sorted(map(str, getattr(model, 'native_decodes', {}))),
        'native_codecs':sorted(map(str, getattr(model, 'native_codecs', {})))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-root',type=Path,required=True)
    p.add_argument('--native-build',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--workload',type=Path,required=True)
    p.add_argument('--engine',choices=['reference','native'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cycles',type=int,default=16)
    p.add_argument('--warmup-cycles',type=int,default=2)
    p.add_argument('--predictor-rope',choices=['native','paired'],default='native')
    p.add_argument('--rotary-head-tile',choices=['4','8','16','auto'],default='4')
    p.add_argument('--audio-delivery',choices=['buffered','inline'],default='buffered')
    args=p.parse_args()
    if args.cycles<1 or args.warmup_cycles<0:
        p.error('positive measured cycles and nonnegative warmup required')
    args.output.mkdir(parents=True,exist_ok=False)
    result={'execution':'INCONCLUSIVE','scope':'bounded direct tick state stress; not HTTP disconnect or performance',
        'engine':args.engine,'slots':16,'measured_cycles':args.cycles,'warmup_cycles':args.warmup_cycles,
        'workload_sha256':sha(args.workload.read_bytes()),'cycles':[],
        'configuration':{'predictor_rope':args.predictor_rope if args.engine=='native' else 'native',
                         'rotary_head_tile':args.rotary_head_tile if args.engine=='native' else None,
                         'audio_delivery':args.audio_delivery if args.engine=='native' else 'reference'}}
    model=None
    try:
        load_reference(args.reference_root)
        sys.path.insert(0,str(args.native_build.resolve()))
        import torch
        import torch_npu
        torch.npu.set_device(0)
        rows=[json.loads(line) for line in args.workload.read_text().splitlines() if line.strip()]
        selected=[rows[i] for i in [*range(8),*range(64,72)]]
        model=create_model(args)
        with torch.inference_mode():
            for cycle in range(args.cycles+args.warmup_cycles):
                if model.states:
                    raise ValueError('state remained before new stress cycle')
                target=args.output/f'cycle-{cycle:02d}'
                target.mkdir()
                streams={}
                chunk_records={}
                generations={i:0 for i in range(16)}
                completions=[]
                cancellations=[]
                def emit(identifier,pcm,rate):
                    if rate!=24000 or not pcm or len(pcm)%2:
                        raise ValueError('invalid stress stream chunk')
                    streams.setdefault(identifier,bytearray()).extend(pcm)
                    chunk_records.setdefault(identifier,[]).append({'bytes':len(pcm),'sha256':sha(pcm)})
                def accept(events):
                    for identifier,event in events:
                        pcm=event['pcm']
                        if event['finish_reason']!='stop' or not pcm:
                            raise ValueError('non-EOS stress completion')
                        if bytes(streams.pop(identifier,bytearray()))!=pcm:
                            raise ValueError('emitted chunks differ from final PCM')
                        file=target/f'{identifier:02d}-g{generations[identifier]}.wav'
                        with wave.open(str(file),'wb') as audio:
                            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(pcm)
                        completions.append({'id':identifier,'generation':generations[identifier],
                            'file':str(file.relative_to(args.output)),'frames':int(event['codec_frames']),
                            'finish_reason':event['finish_reason'],'pcm_bytes':len(pcm),'pcm_sha256':sha(pcm),
                            'chunks':chunk_records.pop(identifier)})
                initial=[(i,dict(payload,instructions='',seed=18000+cycle*32+i,max_new_tokens=2048))
                         for i,payload in enumerate(selected)]
                accept(model.tick(initial,emit))
                accept(model.tick((),emit))
                if completions or len(model.states)!=16:
                    raise ValueError('a request ended before the fixed cancellation boundary')
                cancelled=[1,5,9,13]
                for identifier in cancelled:
                    pcm=bytes(streams.pop(identifier,bytearray()))
                    if len(pcm)!=2*1920*2:
                        raise ValueError('cancellation prefix did not contain two real codec frames')
                    file=target/f'{identifier:02d}-g0-cancel.pcm'
                    file.write_bytes(pcm)
                    cancellations.append({'id':identifier,'generation':0,'status':'CANCELLED',
                        'file':str(file.relative_to(args.output)),'pcm_bytes':len(pcm),'pcm_sha256':sha(pcm)})
                    chunk_records.pop(identifier)
                    generations[identifier]=1
                reuse=[(i,dict(selected[i],instructions='',seed=18000+cycle*32+i+16,max_new_tokens=2048))
                       for i in cancelled]
                accept(model.tick(reuse,emit,cancelled))
                for _ in range(2050):
                    if not model.states:
                        break
                    accept(model.tick((),emit))
                else:
                    raise ValueError('stress frame bound exhausted')
                if len(completions)!=16 or streams or chunk_records or model.states:
                    raise ValueError('stress cycle did not drain exactly16 complete generations')
                torch.npu.synchronize()
                gc.collect()
                row={'cycle':cycle,'warmup':cycle<args.warmup_cycles,'completions':completions,
                    'cancellations':cancellations,'state_after':[],
                    'memory':{'allocated':int(torch.npu.memory_allocated()),'reserved':int(torch.npu.memory_reserved())},
                    'structure':structure(model)}
                result['cycles'].append(row)
                (args.output/'stress.json').write_text(json.dumps(result,indent=2)+'\n')
                print(json.dumps({'cycle':cycle,'complete':len(completions),'cancelled':len(cancellations),
                    'memory':row['memory'],'drained':True}),flush=True)
        result['execution']='COMPLETED'
    except Exception as error:
        result['execution']='FAILED'
        result['failure_kind']='contract' if isinstance(error,ValueError) else 'execution'
        result['error']=f'{type(error).__name__}: {error}'
    finally:
        if model is not None:
            try:
                model.close()
            except Exception as error:
                result['execution']='FAILED'
                result['failure_kind']='cleanup'
                result['cleanup_error']=f'{type(error).__name__}: {error}'
        (args.output/'stress.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'execution':result['execution'],'cycles':len(result['cycles']),
                          'error':result.get('error'),'cleanup_error':result.get('cleanup_error')}),flush=True)
    return 0 if result['execution']=='COMPLETED' else 1


if __name__=='__main__':
    raise SystemExit(main())