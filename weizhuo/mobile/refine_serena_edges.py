"""Stage acoustic boundary repairs. Always review the resulting full sentences.

Measured quiet refinement may move a partition by at most 60ms. A 0.5ms edge
ramp removes PCM discontinuities without cropping samples or cross-fading words.
This is not a phoneme aligner; unresolved loud cuts require new context material.
"""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import wave


def read(path):
    with wave.open(str(path)) as w:
        if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(24000,1,2):raise ValueError('Expected 24k mono PCM16')
        values=array('h',w.readframes(w.getnframes()))
    if sys.byteorder!='little':values.byteswap()
    return values


def quiet_cut(values,guess):
    if guess in (0,len(values)):return guess
    def rms(point):return math.sqrt(sum(v*v for v in values[point-60:point+60])/120)/32768
    points=range(max(60,guess-1440),min(len(values)-60,guess+1440),60)
    quiet=[p for p in points if rms(p)<.002]
    return min(quiet,key=lambda p:abs(p-guess)) if quiet else guess


def declick(values):
    values=array('h',values);count=min(12,len(values)//2) # 0.5ms, not a word cross-fade.
    for end in (False,True):
        if not count or abs(values[-1 if end else 0])<7:continue
        for i in range(count):
            index=len(values)-1-i if end else i
            values[index]=round(values[index]*i/(count-1)) if count>1 else 0
    return values


def trim_quiet_edges(values):
    """Remove only a long measured quiet exterior; keep a 50ms consonant guard."""
    values=array('h',values);hop=240;guard=1200
    energy=[math.sqrt(sum(v*v for v in values[i:i+hop])/len(values[i:i+hop]))/32768 for i in range(0,len(values),hop)]
    first=0;last=len(energy)
    while first<last and energy[first]<.002:first+=1
    while last>first and energy[last-1]<.002:last-=1
    # A short phonetic onset is untouched; only >120ms exterior low energy shrinks.
    start=max(0,first*hop-guard) if first*hop>2880 else 0
    end=min(len(values),last*hop+guard) if len(values)-last*hop>2880 else len(values)
    return values[start:end],dict(start=start,end=end,sourceSamples=len(values),guardSamples=guard)


def refine(base,evidence,directories,output):
    base=Path(base);output=Path(output)
    if output.exists():raise ValueError('Use a new staging directory')
    manifest=json.loads((base/'manifest.json').read_text());records=json.loads(Path(evidence).read_text())['sources']
    lookup={p.name:p for d in directories for p in Path(d).glob('*.wav')};sources={};mapping={};repairs=[]
    shutil.copytree(base,output)
    for record in records:
        for part,name,adjust in zip(record['parts'],record['derivedFiles'],record['adjustments']):
            if name in mapping or not adjust or not (base/name).exists():continue
            source=lookup.get(part['sourceFile'])
            if source is None:raise ValueError('Missing original source: '+part['sourceFile'])
            if source not in sources:sources[source]=read(source)
            values=sources[source];start,end=adjust['adjustedSamples'];old=[start,end]
            start=quiet_cut(values,start);end=quiet_cut(values,end)
            if start>=end:raise ValueError('Nonmonotonic repaired cut')
            gain=adjust['gain'];payload=array('h',(max(-32768,min(32767,round(v*gain))) for v in values[start:end]))
            payload=declick(payload)
            if sys.byteorder!='little':payload.byteswap()
            temp=output/'edge-repair.tmp.wav'
            with wave.open(str(temp),'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(payload.tobytes())
            new=hashlib.sha256(temp.read_bytes()).hexdigest()[:24]+'.wav';temp.rename(output/new);mapping[name]=new
            if new!=name:repairs.append(dict(oldFile=name,file=new,sourceFile=source.name,oldSamples=old,newSamples=[start,end],gain=gain,edgeRampSamples=12))
    # Also eliminate abrupt endpoints on old exact recordings, never trim their frames.
    for f in base.glob('*.wav'):
        if f.name in mapping:continue
        samples=declick(read(f));temp=output/'edge-repair.tmp.wav'
        if sys.byteorder!='little':samples.byteswap()
        with wave.open(str(temp),'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(samples.tobytes())
        new=hashlib.sha256(temp.read_bytes()).hexdigest()[:24]+'.wav';temp.rename(output/new);mapping[f.name]=new
    for key in ('recipes','segments'):
        manifest[key]={text:[mapping.get(n,n) for n in names] for text,names in manifest[key].items()}
    manifest['pause']=mapping.get(manifest['pause'],manifest['pause'])
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    used={n for key in ('recipes','segments') for ns in manifest[key].values() for n in ns}|{manifest['pause']}
    used.update(n for bank in manifest.get('templateBanks',{}).values() for kind in ('prefixes','amounts') for ns in bank.get(kind,{}).values() for n in ns)
    for f in output.glob('*.wav'):
        if f.name not in used:f.unlink()
    from serena_quality import verify_library
    verify_library(output)
    (output/'edge-repairs.json').write_text(json.dumps(repairs,ensure_ascii=False,indent=2))
    return len(repairs)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--source-directory',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print('Changed contextual files:',refine(a.base,a.evidence,a.source_directory,a.output))
