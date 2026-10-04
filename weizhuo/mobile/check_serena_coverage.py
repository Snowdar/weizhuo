"""Check complete numbered announcement families; optionally render realistic auditions."""
import argparse
import hashlib
import json
import re
import subprocess
import wave
from pathlib import Path
from src.weizhuomobile.speech import SerenaClips

FLOW=['新的一局开始了','本局开始，祝大家玩得开心','请选择赢家并结算',
      '所有玩家已准备，可以开始','请助手发底牌','请助手烧一张牌，发三张翻牌',
      '请助手烧一张牌，发一张转牌','请助手烧一张牌，发河牌','等待发牌协助',
      '本轮牌已发好','本局已结算','等待房主确认比牌赢家']
FLOW += [stage+verb for stage in ['底牌','翻牌','转牌','河牌'] for verb in ['已发好','发牌完成']]
ACTIONS=['下注','跟注','闷注','加注','全下','比牌','获得','增加','减少']
CARD_ACTIONS=['弃牌','选择弃牌','看牌','已看牌','过牌','选择过牌','比牌出局']
AMOUNTS=list(range(101))+[125,150,250,350,500,1000,1005,1280,1500,2000,2500,3000,5000,10000,10005,100000,123456789,9007199254740991]


def cases():
    yield from FLOW
    for player in range(1,41):
        who=f'{player}号玩家'
        yield '轮到'+who+'行动';yield '现在请'+who+'行动'
        for action in CARD_ACTIONS:yield who+action
        for action in ACTIONS:
            for amount in (1,20,100,1280,10005):yield who+action+str(amount)+'分'
    for amount in AMOUNTS:
        for verb in ACTIONS:yield f'21号玩家{verb}{amount}分'
        yield f'1号玩家给了2号玩家{amount}分'
        yield f'1号玩家给出{amount}分给2号玩家'
        yield f'2号玩家收了1号玩家的{amount}分'
        yield f'2号玩家从1号玩家收取{amount}分'
        yield f'2号玩家请求收取{amount}分，请确认'
        yield f'2号玩家向3号玩家请求收取{amount}分，请确认'
    yield '1号玩家、2号玩家给了3号玩家、4号玩家各125分'
    yield '1号玩家给出各125分给2号玩家、3号玩家'
    yield '1号玩家向2号玩家、3号玩家各给出125分'
    yield '积分已更新，1号玩家增加100分，2号玩家减少100分'
    yield '本局已结算，1号玩家获得125分，2号玩家获得250分'
    yield '玩家跟注100分'
    # Read the actual App audition, so a later UI text change cannot hide a gap.
    source=(Path(__file__).parent/'src/weizhuomobile/service_navigation.js').read_text()
    match=re.search(r"speech:audition\?'([^']+)'",source)
    if not match:raise ValueError('App audition text not found')
    yield match.group(1)

AUDITIONS=[('free-one','1号玩家给了2号玩家1分'),('free-1280','4号玩家给了3号玩家1280分'),
 ('free-many','1号玩家向2号玩家、3号玩家各给出125分'),('receive','3号玩家从2号玩家收取125分'),
 ('request','2号玩家请求收取95分，请确认'),('score','积分已更新，1号玩家增加100分，2号玩家减少100分'),
 ('blind','4号玩家闷注20分'),('raise','2号玩家加注1280分'),('all-in','3号玩家全下1005分'),
 ('compare','1号玩家比牌50分'),('seen','2号玩家已看牌'),('check','3号玩家选择过牌'),
 ('turn','现在请7号玩家行动'),('turn-large','轮到21号玩家行动'),
 ('start-deal','本局开始，祝大家玩得开心。请助手发底牌。底牌已发好。轮到1号玩家行动'),
 ('settlement','本局已结算，1号玩家获得125分，2号玩家获得250分'),
 ('all-in-one','1号玩家全下1005分'),('all-in-seven','7号玩家全下75分'),
 ('all-in-nineteen','19号玩家全下9999分'),('receive-twenty-one','21号玩家从19号玩家收取99分'),
 ('give-eight','8号玩家给了7号玩家30分'),('give-eighteen','18号玩家给了2号玩家、3号玩家各300分'),
 ('compare-five','5号玩家比牌1280分'),('bet-twenty-one','21号玩家下注95分'),
 ('blind-fifteen','15号玩家闷注100分'),('reduce-seven','7号玩家减少25分'),
 ('award-fifteen','15号玩家获得999分'),('amount-1287','1号玩家给了2号玩家1287分'),
 ('request-outgoing','1号玩家向2号玩家请求收取1分，请确认'),('request-others','3号玩家向4号玩家请求收取1280分，请确认'),
 ('give-29','7号玩家给了2号玩家29分'),('give-30','7号玩家给了2号玩家30分'),('bet-37','2号玩家下注37分'),('give-87','3号玩家给了4号玩家87分'),
 ('large','5号玩家跟注123456789分'),('audition','三号玩家跟注二十分。三号玩家弃牌。本局已结算。')]


def check(base,output=None):
    clips=SerenaClips(base);missing=[];count=0
    emitted=json.loads(subprocess.check_output(['node',str(Path(__file__).parent/'export_serena_events.cjs')],text=True))
    for text in list(cases())+emitted:
        count+=1
        if not clips.plan(text):missing.append(text)
    result=dict(cases=count,realEventSentences=len(emitted),missing=missing,passed=not missing)
    if output:
        output=Path(output);output.mkdir(parents=True,exist_ok=True);rows=[]
        for key,text in AUDITIONS:
            paths=clips.plan(text)
            if not paths:continue
            frames=[];parts=[];samples=0;seams=[]
            for path in paths:
                with wave.open(path) as wav:
                    if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())!=(24000,1,2):raise ValueError('invalid playback audio')
                    pcm=wav.readframes(wav.getnframes())
                parts.append(dict(file=Path(path).name,sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()))
                frames.append(pcm);samples+=len(pcm)//2;seams.append(samples/24000)
            name=key+'.wav'
            with wave.open(str(output/name),'wb') as wav:
                wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(b''.join(frames))
            rows.append(dict(id=key,text=text,file=name,parts=parts,seams=seams[:-1],issues=[]))
        (output/'coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        (output/'report.json').write_text(json.dumps(dict(sources={},examples=rows),ensure_ascii=False,indent=2))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args();r=check(a.base,a.output);print(json.dumps(dict(r,missing=r['missing'][:25]),ensure_ascii=False,indent=2));raise SystemExit(0 if r['passed'] else 1)

if __name__=='__main__':main()
