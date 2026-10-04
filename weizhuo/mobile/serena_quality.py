"""Offline clip quality gates, shared by provisioning and library audits."""
import json
import re
import wave
from pathlib import Path

WARM_INSTRUCT = '自然温暖的年轻女声，桌游播报，每个字的声母韵母都发完整，收音饱满不含糊，中等语速，不要拖尾。只读给定文字。'
CLEAR_INSTRUCT = '字正腔圆的播音员女声，吐字饱满有力，声母清晰，韵母完整，收音扎实不虚，中等语速。只读给定文字。'

def clean_edges(audio, rate=24000):
    """Trim near-zero outer silence only, preserving a 35ms weak-consonant guard."""
    import numpy as np
    x=np.asarray(audio,dtype=np.float64).reshape(-1).copy()
    if not len(x) or not np.isfinite(x).all():raise ValueError('Empty/invalid audio')
    active=np.flatnonzero(np.abs(x)>.00015)
    if not len(active):raise ValueError('Silent audio')
    guard=round(rate*.035)
    start=max(0,int(active[0])-guard);end=min(len(x),int(active[-1])+guard+1)
    x=x[start:end]
    speech=x[np.abs(x)>.002]
    if len(speech):x*=min(.1/np.sqrt(np.mean(speech*speech)),.95/max(np.abs(x)))
    return x,dict(startSamples=start,endSamples=end,sourceSamples=len(audio),guardMs=35)

def duration_bounds(text):
    count=max(1,len(re.sub(r'[，。、！？：;；\s]','',text)))
    if text=='行动':return .55,.95
    if text=='弃牌':return .6,1.0
    if count==1:return .14,.85
    if count==2:return .35,1.25
    return .18*count,.8+.35*count

def wav_duration(path):
    with wave.open(str(path)) as f:
        if f.getnchannels()!=1 or f.getsampwidth()!=2:raise ValueError('requires mono PCM16')
        return f.getnframes()/f.getframerate(),f.getframerate()

def audit_clip(text,path):
    lo,hi=duration_bounds(text)
    try:
        duration,rate=wav_duration(path)
        return dict(duration=round(duration,4),minDuration=lo,maxDuration=hi,sampleRate=rate,passed=lo<=duration<=hi and rate==24000)
    except (OSError,EOFError,wave.Error,ValueError) as error:
        return dict(passed=False,error=str(error),minDuration=lo,maxDuration=hi)

def verify_library(base):
    base=Path(base)
    manifest=json.loads((base/'manifest.json').read_text())
    if manifest.get('methodVersion') in ('context-v1','context-v2'):
        recipes=manifest.get('recipes',{})
        if not recipes or manifest.get('sampleRate')!=24000:raise ValueError('empty/invalid context bank')
        for text,names in recipes.items():
            if not isinstance(names,list) or not 0<len(names)<=16:raise ValueError('invalid context recipe')
            duration=0
            for name in names:
                if not isinstance(name,str) or Path(name).name!=name:raise ValueError('invalid context filename')
                seconds,rate=wav_duration(base/name)
                if rate!=24000 or seconds<=0:raise ValueError('invalid context WAV')
                duration+=seconds
            duration_text=text
            if manifest.get('voiceTerminology',{}).get('spokenSerena')=='All-in':
                duration_text=duration_text.replace('全下','Allin')
            lo,hi=duration_bounds(duration_text)
            if not lo<=duration<=hi:raise ValueError('context duration rejected: '+text)
        segments=manifest.get('segments',{})
        if manifest.get('methodVersion')=='context-v2':
            if not segments:raise ValueError('empty contextual segments')
            for text,names in segments.items():
                if not text or not isinstance(names,list) or not 0<len(names)<=32:raise ValueError('invalid contextual segment')
                for name in names:
                    if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.wav'):raise ValueError('invalid segment filename')
                    seconds,rate=wav_duration(base/name)
                    if rate!=24000 or seconds<=0:raise ValueError('invalid segment WAV')
            name=manifest.get('pause')
            if not isinstance(name,str) or Path(name).name!=name:raise ValueError('invalid clause pause')
            seconds,rate=wav_duration(base/name)
            if rate!=24000 or not 0<seconds<=.2:raise ValueError('invalid clause pause duration')
        families=manifest.get('templateBanks',{})
        if not isinstance(families,dict):raise ValueError('invalid template banks')
        for action,bank in families.items():
            if action not in ('下注','跟注','加注','全下','闷注','比牌','增加','减少') or not isinstance(bank,dict):raise ValueError('invalid template action')
            pairs=bank.get('approvedPairs',{})
            if not isinstance(pairs,dict):raise ValueError('invalid approved template pairs')
            for prefix,amounts in pairs.items():
                if prefix not in bank.get('prefixes',{}) or not isinstance(amounts,list) or not amounts or any(amount not in bank.get('amounts',{}) for amount in amounts):raise ValueError('unavailable approved template pair')
            for kind in ('prefixes','amounts'):
                entries=bank.get(kind,{})
                if not isinstance(entries,dict):raise ValueError('invalid template entries')
                for text,names in entries.items():
                    if not text or not isinstance(names,list) or not 0<len(names)<=16:raise ValueError('invalid template slot')
                    for name in names:
                        if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.wav'):raise ValueError('invalid template slot filename')
                        seconds,rate=wav_duration(base/name)
                        if rate!=24000 or seconds<=0:raise ValueError('invalid template slot WAV')
        return len(recipes)+len(segments)
    clips=manifest['clips']
    if not clips:raise ValueError('empty Serena library')
    rejected=[text for text,name in clips.items() if not audit_clip(text,base/name)['passed']]
    if rejected:raise ValueError('Serena quality gate rejected: '+', '.join(rejected))
    return len(clips)

def normalize_audio(audio):
    import numpy as np
    x=np.asarray(audio,dtype=np.float64).reshape(-1).copy()
    energy=float(np.sqrt(np.mean(x*x)))
    if not len(x) or not np.isfinite(x).all() or energy<1e-9:raise ValueError('silent or invalid audio')
    x*=.1/energy
    maximum=float(np.abs(x).max())
    if maximum>.95:x*=.95/maximum
    return x
