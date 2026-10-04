"""Development-only full-sentence generation, alignment and contextual splice auditions.

Never writes the App voice assets. Alignment timestamps are estimates, not proof of
pronunciation. Preserve source audio and report every cut for subsequent listening.
"""
import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path

PROMPTS = {
    'calm': '正常平静、清晰端正的女声桌游播报。自然适中的语速，稍显利落，但不要快读或赶节奏。每个字完整清楚，整句话顺畅连贯。声音自然饱满，声线稳定，情绪克制，只是正常陈述游戏事实。不兴奋，不叫喊，不撒娇，不妩媚，不做作，不用气声，不拖尾，不朗诵，不刻意升降调。编号、玩家和行动自然连读，正常陈述句收尾。只读给定文字。',
    'brisk': '正常平静、清晰端正的女声桌游播报。语速稍快，比日常交谈略快一点，简洁利落，完整连贯，字头与数字读清。声音自然饱满，声线稳定，情绪克制，只是正常陈述游戏事实。不兴奋，不热情叫喊，不撒娇，不妩媚，不做作，不用气声，不拖音，不朗诵，不刻意升降调。编号、玩家和行动自然连读，正常陈述句收尾。只读给定文字。',
    'mandarin': '自然标准的普通话女声桌游播报。中文咬字清楚地道，声母韵母完整，声调自然，尤其轮到、二号、玩家、行动，不带外国人说中文的口音，不卷舌过度。稳定饱满的中声区，中等语速，语气平静端正，正常陈述事实，整句连贯。不要气声、撒娇、妩媚、兴奋或播音腔。英文 All-in 正常读英语，中文仍保持标准普通话。只读给定文字。',
    'neutral': '清晰端正、自然平实的女声桌游播报员。声音饱满，稳定的中声区，中等语速，情绪克制，陈述事实，整句连贯。编号、玩家和行动连起来说，声线始终一致，正常陈述句收尾。不撒娇，不气声，不妩媚，不刻意婉转，不拖音，不做戏剧化抑扬。只读给定文字。',
    'warm': '自然温暖、饱满清晰的年轻女声，像在桌游中向朋友说明行动。整句话一口气连贯读完，中等语速，音色和音量稳定。每个数字及分字读完整，不用气声，不要夹嗓子，不拖尾，不在现在和请之间停顿。只读给定文字。',
    'clear': '温暖自然的年轻女声，清楚地播报桌游行动，平稳连贯，不夸张抑扬。数字清晰、声母完整，金额和分紧密相连；不要拖音、不要尖细，不把句中词读成独立短句。只读给定文字。',
}
RATE = 24000


def spoken(text):
    return re.sub(r'[\s，。！？、：；,.!?;:]', '', text)


def piece_ranges(text, pieces, words, duration):
    """No guessed splitting of alignment tokens that span two requested pieces."""
    if ''.join(pieces) != spoken(text):
        raise ValueError('Pieces must cover the complete spoken text')
    if len(pieces) == 1:
        if duration <= 0:
            raise ValueError('Empty whole recording')
        return [(0.0, duration)]
    positions = {}; cursor = 0; previous = 0.0
    for word in words:
        token = spoken(word['word'])
        if not token:
            continue
        start, end = float(word['start']), float(word['end'])
        if not (0 <= start <= end <= duration + .025) or start < previous - .025:
            raise ValueError('Non-monotonic/out-of-bounds alignment')
        positions[cursor] = (start, 'start')
        cursor += len(token)
        positions.setdefault(cursor, (end, 'end'))
        previous = end
    if ''.join(spoken(w['word']) for w in words) != spoken(text):
        raise ValueError('Alignment text does not match source')
    cuts = [0.0]; cursor = 0
    for piece in pieces[:-1]:
        cursor += len(piece)
        if cursor not in positions:
            raise ValueError('Alignment token crosses a cut; use a larger piece')
        # Contiguous source slices: no overlap, missing samples or duplicated syllables.
        cuts.append(positions[cursor][0])
    cuts.append(duration)
    if any(b <= a for a, b in zip(cuts, cuts[1:])):
        raise ValueError('Empty/non-monotonic piece')
    return list(zip(cuts, cuts[1:]))


def quiet_boundaries(pcm,ranges,rate=RATE):
    """Refine estimated word cuts only inside a measured quiet pause.

    Search at most 150ms either side. Preserve every sample in the partition;
    never create overlap, trim a word or infer a boundary inside a loud syllable.
    """
    import numpy as np
    cuts=[0];window=max(1,round(rate*.005));guard=round(rate*.15)
    x=np.asarray(pcm,dtype=np.float64)/32768
    for _,end in ranges[:-1]:
        guess=round(end*rate)
        points=range(max(cuts[-1]+window,guess-guard),min(len(x)-window,guess+guard),max(1,window//2))
        quiet=[point for point in points if np.sqrt(np.mean(x[point-window//2:point+window//2]**2))<.002]
        if not quiet:raise ValueError('No measured quiet boundary; retain the whole sentence or expand the slot')
        cut=min(quiet,key=lambda point:abs(point-guess))
        if cut<=cuts[-1]:raise ValueError('Non-monotonic acoustic cut')
        cuts.append(cut)
    cuts.append(len(x))
    return [(a/rate,b/rate) for a,b in zip(cuts,cuts[1:])]


def load_aligner(path, processor='openai/whisper-tiny'):
    import mlx.core as mx
    import mlx.nn as nn
    from mlx.utils import tree_unflatten
    from transformers import WhisperProcessor
    from mlx_audio.stt.models.whisper.whisper import Model, ModelDimensions
    config = json.loads((path / 'config.json').read_text())
    quantization = config.pop('quantization')
    config.pop('model_type', None)
    model = Model(ModelDimensions.from_dict(config), mx.float16)
    weights = mx.load(str(path / 'model.safetensors'))
    weights.pop('alignment_heads', None)
    nn.quantize(model, **quantization, class_predicate=lambda p, v:
                isinstance(v, (nn.Linear, nn.Embedding)) and p + '.scales' in weights)
    model.update(tree_unflatten(list(weights.items())))
    mx.eval(model.parameters())
    model._processor = WhisperProcessor.from_pretrained(processor, local_files_only=True)
    model.set_alignment_heads([[2, 2], [3, 0], [3, 2], [3, 3], [3, 4], [3, 5]])
    return model


def align(model, audio, text):
    import numpy as np
    import mlx.core as mx
    from scipy.signal import resample_poly
    from mlx_audio.stt.models.whisper.timing import find_alignment
    mel, frames = model._prepare_audio(resample_poly(audio, 2, 3).astype(np.float32))
    tokenizer = model.get_tokenizer(language='zh')
    timing = find_alignment(model, tokenizer, tokenizer.encode(text), mel[:3000].astype(mx.float16), frames)
    return [dict(word=w.word, start=float(w.start), end=float(w.end),
                 probability=float(w.probability)) for w in timing]


def fingerprint(row, prompt, seed, max_tokens=256):
    settings=[row, prompt, seed] + ([dict(maxTokens=max_tokens)] if max_tokens!=256 else [])
    return hashlib.sha256(json.dumps(settings, ensure_ascii=False,
                                    sort_keys=True).encode()).hexdigest()[:20]


def append_scenarios(plan, scenarios):
    """Retain coherent game fixtures, but synthesize every sentence in context."""
    for scenario in scenarios['scenarios']:
        for index, parts in enumerate(scenario['sentences'],1):
            pieces=[spoken(part) for part in parts]
            text=''.join(pieces)+'。'
            sid='scenario-'+scenario['id']+'-'+str(index)
            plan['sources'].append(dict(id=sid,text=text,pieces=pieces))
            plan['examples'].append(dict(id=sid,parts=[[sid,i] for i in range(len(pieces))],reference=sid))
    return plan


def candidate_combinations(options, limit):
    # Compare complete original takes before mixing different recordings.
    # A Cartesian prefix alone otherwise keeps most slots on take zero.
    seen=set();count=0
    original=(tuple(option[index] for option in options) for index in range(min(map(len,options),default=0)))
    for selected in itertools.chain(original,itertools.product(*options)):
        key=tuple(part['file'] for part in selected)
        if key in seen:continue
        seen.add(key);yield selected;count+=1
        if count>=limit:return


def main():
    import numpy as np
    from scipy.io.wavfile import read, write
    from serena_quality import clean_edges, duration_bounds
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--aligner', type=Path, required=True)
    parser.add_argument('--processor', default='openai/whisper-tiny', help='Local Whisper processor directory or cached model ID')
    parser.add_argument('--plan', type=Path, default=Path(__file__).with_name('serena_template_plan.json'))
    parser.add_argument('--plan-batch', help='Named batch in a saved multi-batch generation plan')
    parser.add_argument('--scenario-file',type=Path,help='Additional coherent game sentences, generated as complete sentences')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed-base', type=int, default=8400, help='First deterministic generation seed, saved in provenance')
    parser.add_argument('--max-tokens', type=int, default=256, help='Generation budget; longer contextual narration needs a larger budget')
    parser.add_argument('--takes', type=int, default=2)
    parser.add_argument('--variants', type=int, default=4, help='Maximum candidate combinations per example')
    parser.add_argument('--prompt', choices=PROMPTS, default='warm')
    parser.add_argument('--quiet-boundaries',action='store_true',help='Place cuts in measured quiet pauses near estimated word boundaries')
    parser.add_argument('--reuse-sources', action='store_true', help='Reuse cached sources; no TTS generation')
    parser.add_argument('--transcribe', action='store_true', help='Blind local Whisper text check on final splices')
    args = parser.parse_args()
    if args.takes < 1 or args.variants < 1:
        parser.error('takes and variants must be positive')
    out = args.output; out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(args.plan.read_text())
    if args.plan_batch:
        if args.plan_batch not in plan:parser.error('Unknown generation plan batch')
        plan=plan[args.plan_batch]
    if args.scenario_file:append_scenarios(plan,json.loads(args.scenario_file.read_text()))
    prompt = PROMPTS[args.prompt]
    tts = None
    sources = {}
    for row in plan['sources']:
        if re.search(r'\d', row['text']):
            raise ValueError('Spell numeric values in Chinese before contextual generation: ' + row['id'])
        candidates = []
        for take in range(args.takes):
            seed = args.seed_base + take
            key = fingerprint(row, prompt, seed, args.max_tokens)
            wav = out / f'{key}.wav'; metadata = out / f'{key}.json'
            if not wav.exists() or not metadata.exists():
                if args.reuse_sources:
                    raise ValueError('Missing cached source ' + row['id'])
                import mlx.core as mx
                from mlx_audio.tts.utils import load_model
                if tts is None:
                    tts = load_model(str(args.model))
                mx.random.seed(seed)
                # Only complete sentences are ever sent to Qwen.
                chunks = list(tts.generate_custom_voice(text=row['text'], speaker='Serena',
                    language='Chinese', instruct=prompt, temperature=.4, max_tokens=args.max_tokens))
                if not chunks or any(c.sample_rate != RATE for c in chunks):
                    raise ValueError('Unexpected sample rate')
                raw = np.concatenate([np.asarray(c.audio).reshape(-1) for c in chunks])
                write(out / f'{key}-raw.wav', RATE, (np.clip(raw, -1, 1) * 32767).astype(np.int16))
                audio, trim = clean_edges(raw, RATE)
                write(wav, RATE, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
                metadata.write_text(json.dumps(dict(text=row['text'], prompt=prompt, seed=seed,
                    file=wav.name, trim=trim, model=args.model.name,maxTokens=args.max_tokens), ensure_ascii=False, indent=2))
            rate, pcm = read(wav)
            if rate != RATE or pcm.ndim != 1 or pcm.dtype != np.int16:
                raise ValueError('Requires 24k mono PCM16')
            duration = len(pcm) / RATE; lo, hi = duration_bounds(row['text'])
            candidates.append(dict(file=wav.name, key=key, duration=duration,
                                   durationPassed=lo <= duration <= hi))
            print('source', row['id'], take, round(duration, 3), flush=True)
        sources[row['id']] = dict(row=row, candidates=candidates)
    # Release the large generation model before loading the small alignment model.
    del tts
    aligner = load_aligner(args.aligner, args.processor)
    pieces = {}; source_report = {}
    for sid, source in sources.items():
        attempts = []
        for candidate in source['candidates']:
            if not candidate['durationPassed']:
                attempts.append(dict(candidate, rejected='duration')); continue
            rate, pcm = read(out / candidate['file']); audio = pcm.astype(np.float32) / 32768
            # Whole recordings need no forced cut alignment; validate speech independently.
            whole = len(source['row']['pieces']) == 1
            words = [] if whole else align(aligner, audio, spoken(source['row']['text']))
            try:
                ranges = piece_ranges(source['row']['text'], source['row']['pieces'], words, len(audio) / RATE)
                if args.quiet_boundaries and not whole:ranges=quiet_boundaries(pcm,ranges)
            except ValueError as error:
                attempts.append(dict(candidate, alignment=words, rejected=str(error))); continue
            parts = []
            for index, (text, (start, end)) in enumerate(zip(source['row']['pieces'], ranges)):
                a, b = round(start * RATE), round(end * RATE)
                name = f'{candidate["key"]}-piece{index}.wav'
                write(out / name, RATE, pcm[a:b])
                parts.append(dict(text=text, file=name, sourceFile=candidate['file'],
                                  sourceId=sid, samples=[a, b], position=index,cutMethod='whole recording; no internal cut' if whole else ('estimated alignment + measured quiet pause' if args.quiet_boundaries else 'estimated alignment')))
            # Partitioning a sentence must reconstruct it sample-for-sample.
            rebuilt = np.concatenate([pcm[p['samples'][0]:p['samples'][1]] for p in parts])
            if not np.array_equal(rebuilt, pcm):
                raise ValueError('Partition loses/duplicates source samples')
            attempts.append(dict(candidate, alignment=words, parts=parts,
                status='alignment_candidate_not_listening_approved'))
            # Timing gate is provisional; retain all alternatives, never claim quality approval.
            if sid not in pieces:
                pieces[sid] = parts
        source_report[sid] = attempts
    expanded = []
    for example in plan['examples']:
        options = [[attempt['parts'][index] for attempt in source_report[sid] if attempt.get('parts')]
                   for sid, index in example['parts']]
        for number, selected in enumerate(candidate_combinations(options, args.variants)):
            expanded.append(dict(example, selected=list(selected), baseId=example['id'],
                                 id=example['id'] + (f'-variant{number + 1}' if number else '')))
        if any(not option for option in options):
            expanded.append(dict(example, selected=None))
    rows = []; playlist = []
    for example in expanded:
        selected = example['selected']
        if selected:
            arrays = [read(out / p['file'])[1] for p in selected]
            pcm = np.concatenate(arrays)
            seams = np.cumsum([len(a) for a in arrays])[:-1]
            issues = []
            for index,pos in enumerate(seams):
                left,right=selected[index:index+2]
                # Adjacent cuts of the same recording are its original waveform,
                # not a new junction. A normal waveform slope is not a splice defect.
                if left['sourceFile']==right['sourceFile'] and left['samples'][1]==right['samples'][0]:continue
                if abs(int(pcm[pos]) - int(pcm[pos - 1])) / 32768 > .08:
                    issues.append(dict(kind='junction_discontinuity', seconds=round(pos / RATE, 4)))
            name = example['id'] + '.wav'; write(out / name, RATE, pcm)
            expected = ''.join(p['text'] for p in selected)
            asr = None
            if args.transcribe:
                # No expected words or prompt supplied to the recognizer.
                from src.weizhuomobile.speech import chinese_number
                result = aligner.generate(str(out / name), language='zh', temperature=0,
                    condition_on_previous_text=False, return_timestamps=True, verbose=False,
                    sample_len=min(100, 12 + 4 * len(expected)))
                transcript = str(result.text)
                normalized = spoken(re.sub(r'\d+', lambda m: chinese_number(m.group()), transcript))
                asr = dict(transcript=transcript, textMatch=normalized == expected,
                           unreliable=len(normalized) > max(20, 2 * len(expected)),
                           engine='local whisper-tiny 4bit; advisory, not a listening verdict')
            rows.append(dict(id=example['id'], text=''.join(p['text'] for p in selected),
                baseId=example['baseId'],
                file=name, parts=selected, seams=[round(s / RATE, 4) for s in seams],
                issues=issues, asr=asr, status='asr_flagged_needs_review' if asr and not asr['textMatch'] else 'needs_audio_review',
                reference=example.get('reference')))
            playlist.extend([pcm, np.zeros(round(RATE * .65), dtype=np.int16)])
            continue
        rows.append(dict(id=example['id'], status='rejected_missing_safe_alignment'))
    if playlist:
        write(out / 'all-examples.wav', RATE, np.concatenate(playlist))
    report = dict(method='whole sentence -> estimated alignment -> contiguous context cuts -> no-gap splice',
        sampleRate=RATE, prompt=prompt, sources=source_report, examples=rows,
        verification='No listening approval. Forced alignment does not verify text; optional blind ASR is a separate advisory check.')
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('Context auditions saved:', out, flush=True)


if __name__ == '__main__':
    main()
