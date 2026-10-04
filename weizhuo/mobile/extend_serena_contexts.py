"""Developer-only context reuse from reviewed whole sentences; no TTS generation."""
import argparse
import hashlib
import json
from pathlib import Path


def build(bank, plan, output, aligner_path, processor):
    import numpy as np
    from scipy.io.wavfile import read, write
    from serena_templates import load_aligner, align, piece_ranges
    manifest=json.loads((bank/'manifest.json').read_text())
    evidence={r['text']:r for r in json.loads((bank/'review-evidence.json').read_text())}
    if manifest.get('methodVersion')!='context-v1':raise ValueError('Requires a reviewed contextual bank')
    output.mkdir(parents=True,exist_ok=True);pieces={};model=None;source_report={}
    for source in plan['sources']:
        text=source['text'];names=manifest['recipes'][text]
        pcm=[];hashes=[]
        for name in names:
            if Path(name).name!=name:raise ValueError('Invalid source filename')
            path=bank/name;rate,data=read(path)
            if rate!=24000 or data.ndim!=1 or data.dtype!=np.int16:raise ValueError('Invalid reviewed source WAV')
            pcm.append(data);hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        if 'pieces' in source:
            whole=np.concatenate(pcm)
            if model is None:model=load_aligner(aligner_path,processor)
            words=align(model,whole.astype(np.float32)/32768,text)
            ranges=piece_ranges(text,source['pieces'],words,len(whole)/24000)
            chunks=[whole[round(a*24000):round(b*24000)] for a,b in ranges]
            if not np.array_equal(np.concatenate(chunks),whole):raise ValueError('Cuts do not reproduce reviewed recording')
            labels=source['pieces']
        else:
            chunks=pcm;labels=[p['text'] for p in evidence[text]['parts']];words=[]
            if len(labels)!=len(chunks):raise ValueError('Review metadata differs from recipe')
        source_report[source['id']]=dict(text=text,sourceHashes=hashes,alignment=words)
        for index,(label,chunk) in enumerate(zip(labels,chunks)):
            filename=f'source-{len(pieces)}.wav';write(output/filename,24000,chunk)
            pieces[source['id'],index]=(chunk,dict(text=label,file=filename,sourceSentence=text,sourceHashes=hashes))
    rows=[]
    for example in plan['examples']:
        selected=[pieces[sid,index] for sid,index in example['parts']]
        joined=np.concatenate([pcm for pcm,_ in selected]);seams=np.cumsum([len(pcm) for pcm,_ in selected])[:-1]
        issues=[dict(kind='junction_discontinuity',seconds=round(pos/24000,4)) for pos in seams if abs(int(joined[pos])-int(joined[pos-1]))/32768>.08]
        filename=example['id']+'.wav'
        if Path(filename).name!=filename:raise ValueError('Invalid example ID')
        write(output/filename,24000,joined)
        rows.append(dict(id=example['id'],file=filename,text=''.join(part['text'] for _,part in selected),parts=[part for _,part in selected],seams=[round(pos/24000,4) for pos in seams],issues=issues))
    # Original source reference is omitted: a different amount is not a same-text comparison.
    report=dict(method='reviewed context reuse -> contiguous cuts -> no-gap splice',sources={},sourceEvidence=source_report,examples=rows)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return len(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank',type=Path,required=True);parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--aligner',type=Path,required=True)
    parser.add_argument('--processor',required=True)
    args=parser.parse_args()
    print('Context candidates:',build(args.bank,json.loads(args.plan.read_text()),args.output,args.aligner,args.processor))

if __name__=='__main__':main()
