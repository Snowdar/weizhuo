"""Export reviewed whole-sentence context cuts as a composable Serena bank.

Generation/review directories are development inputs, never bundled in the App.
Each selected source must have a passing audio review and matching SHA256.
"""
import argparse
import hashlib
import fnmatch
from array import array
import sys
import math
import json
import shutil
import tempfile
import wave
from pathlib import Path


def export(base, directories, output, cut_shift_ms=0, cut_profile=None, trim_context_silence=False, level_context=False, preferred_whole=(), preferred_sources=()):
    base=Path(base);output=Path(output)
    manifest=json.loads((base/'manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='serena-context-bank-') as tmp:
        stage=Path(tmp);segments={};evidence=[]
        def copy(source):
            name=hashlib.sha256(source.read_bytes()).hexdigest()[:24]+'.wav'
            shutil.copy2(source,stage/name)
            return name
        shifted={}
        def contextual_part(directory,part):
            amount=next((value for key,value in (cut_profile or {}).items() if fnmatch.fnmatch(part['sourceId'],key)),cut_shift_ms)
            if not amount and not trim_context_silence and not level_context:return directory/part['file']
            source=directory/part['sourceFile']
            with wave.open(str(source)) as wav:pcm=wav.readframes(wav.getnframes());total=len(pcm)//2
            start,end=part['samples'];shift=round(amount*24)
            start=start+shift if start else 0;end=end+shift if end<total else total
            if not 0<=start<end<=total:raise ValueError('Adjusted cut out of bounds')
            untrimmed=[start,end]
            if trim_context_silence:
                values=array('h',pcm[start*2:end*2])
                if sys.byteorder!='little':values.byteswap()
                active=[index for index,value in enumerate(values) if abs(value)>5]
                if active:
                    # Only near-zero exterior samples, with the original 35ms guard.
                    guard=840;origin=start
                    start=origin+max(0,active[0]-guard)
                    end=origin+min(len(values),active[-1]+guard+1)

            payload=pcm[start*2:end*2];gain=1.0
            if level_context:
                values=array('h',payload)
                if sys.byteorder!='little':values.byteswap()
                active=[value for value in values if abs(value)>66]
                if active:
                    rms=math.sqrt(sum(value*value for value in active)/len(active))
                    gain=min(2.0,max(.5,3276.8/rms),31128/max(abs(value) for value in values))
                    values=array('h',(round(value*gain) for value in values))
                    if sys.byteorder!='little':values.byteswap()
                    payload=values.tobytes()
            path=stage/('adjusted-'+hashlib.sha256((str(source)+str((start,end))).encode()).hexdigest()[:20]+'.wav')
            with wave.open(str(path),'wb') as wav:
                wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(payload)
            shifted[part['file']]=dict(originalSamples=part['samples'],adjustedSamples=[start,end],shiftMs=amount,untrimmedSamples=untrimmed,trimmedExteriorSilence=trim_context_silence,gain=gain)
            return path
        recipes={text:[copy(base/name) for name in names] for text,names in manifest['recipes'].items()}
        template_banks={}
        for action,bank in manifest.get('templateBanks',{}).items():
            template_banks[action]=dict(bank,**{kind:{text:[copy(base/name) for name in names] for text,names in bank.get(kind,{}).items()} for kind in ('prefixes','amounts')})
        segments.update({text:[copy(base/name) for name in names] for text,names in manifest.get('segments',{}).items()});segments.update(recipes)
        for directory in directories:
            directory=Path(directory)
            report=json.loads((directory/'report.json').read_text())
            reviews={r['id']:r for r in json.loads((directory/'audio-review.json').read_text())}
            selected={}
            for row in report['examples']:
                review=reviews.get(row['id'],{})
                if review.get('status')!='model_shortlisted_needs_human_listening' or row.get('issues'):continue
                path=directory/row['file']
                if hashlib.sha256(path.read_bytes()).hexdigest()!=review['sha256']:raise ValueError('Reviewed audio changed')
                sid=row.get('baseId',row['id'])
                if sid.startswith('digits-') or sid in selected:continue
                selected[sid]=row
                frames=[]
                for part in row['parts']:
                    with wave.open(str(directory/part['file'])) as wav:
                        if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())!=(24000,1,2):raise ValueError('Invalid context PCM')
                        frames.append(wav.readframes(wav.getnframes()))
                with wave.open(str(path)) as wav:
                    if b''.join(frames)!=wav.readframes(wav.getnframes()):raise ValueError('Cuts no longer reproduce reviewed whole source')
                # A complete source also remains available as the longest match.
                names=[copy(contextual_part(directory,p)) for p in row['parts']]
                if len(names)==1:segments.setdefault(row['text'],names)
                elif sid in preferred_whole:
                    # Keep reviewed complete common source text as one buffer;
                    # the variable parts are still exported for other numbers.
                    original=directory/row['file']
                    segments.setdefault(row['text'],[copy(original)])
                for part,name in zip(row['parts'],names):
                    if sid in preferred_sources:segments[part['text']]=[name]
                    else:segments.setdefault(part['text'],[name])
                # Preserve actor + action from the same recording where available.
                if sid.startswith('player-') and len(names)==3:
                    segments.setdefault(''.join(p['text'] for p in row['parts'][:2]),names[:2])
                evidence.append(dict(source=sid,text=row['text'],sha256=review['sha256'],
                    review=review,parts=row['parts'],cutShiftMs=cut_shift_ms,cutProfile=cut_profile,trimContextSilence=trim_context_silence,levelContext=level_context,derivedFiles=names,adjustments=[shifted.get(p['file']) for p in row['parts']]))
        pause=stage/'clause-pause.wav'
        with wave.open(str(pause),'wb') as wav:
            wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(b'\0\0'*2400)
        new=dict(manifest,methodVersion='context-v2',segments=segments,templateBanks=template_banks,pause=pause.name,
            assembly='Longest contextual phrase, complete common amount+unit, numeric context cuts for other integers; punctuation pause only')
        (stage/'manifest.json').write_text(json.dumps(new,ensure_ascii=False,indent=2))

        from serena_quality import verify_library
        verify_library(stage)
        used={name for values in recipes.values() for name in values}|{name for values in segments.values() for name in values}|{pause.name}
        used.update(name for bank in template_banks.values() for kind in ('prefixes','amounts') for names in bank[kind].values() for name in names)
        for path in stage.glob('*.wav'):
            if path.name not in used:path.unlink()
        evidence=[row for row in evidence if any(name in used for name in row.get('derivedFiles',[]))]
        (stage/'review-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
        if output.exists():raise ValueError('Export to a new directory, then adopt after assembled sentence review')
        shutil.copytree(stage,output)
    return len(segments)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True)
    p.add_argument('--prefer-source',action='append',default=[],help='Explicitly select a reviewed source for duplicate context tokens');p.add_argument('--prefer-whole',action='append',default=[],help='Explicitly retain an approved complete source by ID; contextual variables are also exported');p.add_argument('--level-context',action='store_true',help='Bounded speech RMS gain per context, no pitch/speed change; assembled review required');p.add_argument('--trim-context-silence',action='store_true',help='Trim near-zero exterior context silence offline with 35ms guard; assembled review required');p.add_argument('--cut-profile',type=Path,help='Explicit source-family cut candidates, require assembled review');p.add_argument('--cut-shift-ms',type=float,default=0,help='Development cut candidate; assembled audition approval is still required');p.add_argument('--directory',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print('Context phrases:',export(a.base,a.directory,a.output,a.cut_shift_ms,json.loads(a.cut_profile.read_text()) if a.cut_profile else None,a.trim_context_silence,a.level_context,a.prefer_whole,a.prefer_source))

if __name__=='__main__':main()
