"""Four local announcers; generation and playback remain outside server work."""
import json
import re
import sys
from pathlib import Path

VOICE_NAMES={0:'系统 · 清晰',1:'离线 · 松朗',2:'离线 · 悦然',3:'Serena · 暖语'}
def announcer_text(text):
    # Older pages may still attach a nickname. All engines receive the same text.
    return re.sub(r'((?:\d+|[零一二三四五六七八九十百千万亿]+)号玩家)，[^，]*，',r'\1',str(text))

def chinese_number(n):
    n=int(n)
    if n<0:return '负'+chinese_number(-n)
    if n<10:return '零一二三四五六七八九'[n]
    if n<100:return ('' if n//10==1 else chinese_number(n//10))+'十'+(chinese_number(n%10) if n%10 else '')
    for base,unit in ((100000000,'亿'),(10000,'万'),(1000,'千'),(100,'百')):
        if n>=base:
            q,r=divmod(n,base)
            return chinese_number(q)+unit+('零' if r and r<base//10 else '')+(chinese_number(r) if r else '')

class SerenaClips:
    def __init__(self,base):
        self.base=Path(base)
        self.recipes={};self.segments={};self.template_banks={};self.pause=None;self.context_only=False
        try:
            manifest=json.loads((self.base/'manifest.json').read_text())
            self.clips=manifest.get('clips',{})
            self.recipes=manifest.get('recipes',{})
            self.segments=manifest.get('segments',{})
            self.template_banks=manifest.get('templateBanks',{})
            self.pause=manifest.get('pause')
            self.context_only=manifest.get('methodVersion') in ('context-v1','context-v2')
        except (OSError,ValueError,KeyError):self.clips={}
        self.tokens=sorted(self.clips,key=len,reverse=True)
        self.context_tokens=sorted((key for key in self.segments if key),key=len,reverse=True)
        self.context_by_initial={}
        for key in self.context_tokens:self.context_by_initial.setdefault(key[0],[]).append(key)
    def plan(self,text):
        # Fixed recordings identify players by number; names stay visible in the UI.
        text=announcer_text(text)
        text=re.sub(r'\d+',lambda m:chinese_number(m.group()),text)
        original=text
        text=re.sub(r'[，。、！？：;；\s]','',text)
        if text in self.recipes:
            names=self.recipes[text]
            if not isinstance(names,list) or not 0<len(names)<=16:return None
            paths=[]
            for name in names:
                if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.wav'):return None
                path=self.base/name
                if not path.is_file():return None
                paths.append(str(path))
            return paths
        family=self._template_plan(text)
        if family:return family
        if self.segments:return self._context_plan(original)
        if self.context_only:return None
        result=[]
        while text:
            token=next((t for t in self.tokens if text.startswith(t.replace('，',''))),None)
            if token is None:return None  # Unknown phrase; caller keeps text and chime without changing timbre.
            result.append(str(self.base/self.clips[token]));text=text[len(token.replace('，','')):]
        return result if 0<len(result)<=120 else None


    def _template_plan(self,text):
        # Amounts belong to an action's recording cohort. Never borrow a
        # similarly spelled amount from another action or guess a missing value.
        match=re.fullmatch(r'([零一二三四五六七八九十百千万亿]+号玩家)(下注|跟注|加注|全下|闷注|比牌|增加|减少)([零一二三四五六七八九十百千万亿]+分)',text)
        if not match or not isinstance(self.template_banks,dict):return None
        actor,action,amount=match.groups();bank=self.template_banks.get(action)
        if not isinstance(bank,dict):return None
        prefixes=bank.get('prefixes',{});amounts=bank.get('amounts',{})
        if not isinstance(prefixes,dict) or not isinstance(amounts,dict):return None
        approved=bank.get('approvedPairs',{})
        if not isinstance(approved,dict):return None
        allowed=approved.get(actor+action,[])
        if not isinstance(allowed,list) or amount not in allowed:return None
        prefix=prefixes.get(actor+action);suffix=amounts.get(amount)
        if not isinstance(prefix,list) or not isinstance(suffix,list) or not prefix or not suffix:return None
        names=prefix+suffix
        if len(names)>16:return None
        paths=[]
        for name in names:
            if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.wav'):return None
            path=self.base/name
            if not path.is_file():return None
            paths.append(str(path))
        return paths

    def _context_plan(self,text):
        result=[];compact='';boundaries=set()
        for char in text:
            if char in '，。！？；;、':boundaries.add(len(compact))
            elif char not in '：' and not char.isspace():compact+=char
        # Long prefixes can overlap another valid action (比牌 / 比牌出局).
        # Minimize buffer junctions across a completely covered suffix; prefer the
        # longer contextual phrase when the number of junctions is equal.
        covered={len(compact):None};costs={len(compact):0}
        for offset in range(len(compact)-1,-1,-1):
            for token in self.context_by_initial.get(compact[offset],[]):
                end=offset+len(token)
                if end not in covered or not compact.startswith(token,offset):continue
                names=self.segments[token]
                if not isinstance(names,list) or not names:continue
                cost=len(names)+costs[end]
                if offset not in costs or cost<costs[offset]:
                    covered[offset]=(end,names);costs[offset]=cost
        if 0 not in covered:return None
        offset=0
        while offset<len(compact):
            offset,names=covered[offset];result.extend(names)
            # A whole phrase spanning a comma already contains its recorded pause.
            if offset in boundaries and offset<len(compact) and self.pause:result.append(self.pause)
        if not 0<len(result)<=1024:return None
        paths=[]
        for name in result:
            if not isinstance(name,str) or Path(name).name!=name or not name.endswith('.wav'):return None
            path=self.base/name
            if not path.is_file():return None
            paths.append(str(path))
        return paths


from .platforms import is_android

class Speaker:
    def __init__(self):
        self.native=None;self.system=None;self.system_queue=False;self.offline=False;self.voice=0;self.clips=None;self._status=''
        if is_android():
            from java import jclass
            activity=jclass('org.beeware.android.MainActivity').singletonThis
            self.system=jclass('com.snowdar.weizhuomobile.WeizhuoSpeaker')(activity)
            self.native=self.system;self.system_queue=True
            try:self.voice=int(self.native.getVoice())
            except (TypeError,ValueError):self.voice=2
        elif sys.platform=='ios':
            from ctypes import CDLL
            CDLL('/System/Library/Frameworks/AVFoundation.framework/AVFoundation')
            from rubicon.objc import ObjCClass
            try:
                self.system=ObjCClass('WZSystemSpeaker').alloc().init();self.system_queue=True
            except NameError:self.system=ObjCClass('AVSpeechSynthesizer').alloc().init()
            try:
                candidate=ObjCClass('WZOfflineSpeaker').sharedSpeaker()
                if candidate.available():
                    self.native=candidate;self.offline=True;self.voice=int(candidate.voice)
                    base=ObjCClass('NSBundle').mainBundle.pathForResource('Voice',ofType=None)
                    self.clips=SerenaClips(str(base)+'/Serena')
            except NameError:pass
            if self.native is None:self.native=self.system
            prefs=ObjCClass('NSUserDefaults').standardUserDefaults
            saved=prefs.objectForKey('weizhuo.announcer')
            # objectForKey returns an NSNumber proxy on a real device, not an int.
            # Use the typed accessor; optional preferences must never block startup.
            if saved is not None:
                try:
                    selected=int(prefs.integerForKey('weizhuo.announcer'))
                    if selected in self.choices:self.voice=selected
                except (TypeError,ValueError,OverflowError):pass
            if self.offline and self.voice in (1,2):self.native.setVoice(self.voice)
    @property
    def choices(self):
        if is_android() and self.native:
            self.offline=bool(self.native.available())
            base=str(self.native.getVoicePath())
            if base and self.clips is None and (Path(base)/'Serena/manifest.json').exists():self.clips=SerenaClips(Path(base)/'Serena')
        return [0]+([1,2] if self.offline else [])+([3] if self.clips and (self.clips.clips or self.clips.recipes or self.clips.segments) else [])
    @property
    def ready(self):
        # One playback lane, with waiting/expiry in JS.
        if self.offline and self.native.busy():return False
        return not (self.system.busy() if self.system_queue else self.system.isSpeaking()) if self.system else False
    @property
    def status(self):
        if self._status:return self._status
        if is_android() and self.native:return str(self.native.getStatus())
        if self.offline and self.voice!=0:return str(self.native.status)
        return '系统音色' if self.native else '语音不可用'
    def say(self,text):
        if not self.native:return
        text=announcer_text(text)[:1000];self._status=''
        if self.offline and self.voice in (1,2):
            self.native.speakText(text);return
        if self.voice==3:
            plan=self.clips.plan(text) if self.clips else None
            if plan:
                payload={'paths':plan,'preserveSamples':True} if self.clips.context_only else plan
                self.native.speakClipPaths(json.dumps(payload,ensure_ascii=False));return
            self._status='暖语暂未覆盖本句，请查看文字记录'
            return  # Keep the selected timbre; scoring notifications still supply a chime.
        self.system_say(text)
    def system_say(self,text):
        if self.system_queue:
            self.system.speakText(text);return
        from rubicon.objc import ObjCClass
        utterance=ObjCClass('AVSpeechUtterance').speechUtteranceWithString(text)
        available=[v for v in ObjCClass('AVSpeechSynthesisVoice').speechVoices() if str(v.language).startswith('zh-CN')]
        utterance.voice=max(available,key=lambda v:int(v.quality)) if available else ObjCClass('AVSpeechSynthesisVoice').voiceWithLanguage('zh-CN')
        utterance.rate=.48;utterance.pitchMultiplier=1.0
        utterance.preUtteranceDelay=.04;utterance.postUtteranceDelay=.10
        # AVSpeechSynthesizer queues utterances; do not interrupt the previous action.
        self.system.speakUtterance(utterance)
    def set_voice(self,voice):
        if not isinstance(voice,(int,float)) or isinstance(voice,bool) or voice not in self.choices:return
        voice=int(voice)
        if voice!=self.voice:self.stop()
        self.voice=voice;self._status=''
        if is_android():self.native.setVoice(voice)
        elif self.offline and voice in (1,2):self.native.setVoice(voice)
        if sys.platform=='ios':
            from rubicon.objc import ObjCClass
            ObjCClass('NSUserDefaults').standardUserDefaults.setInteger(voice,forKey='weizhuo.announcer')
    def stop(self):
        if self.offline:self.native.stop()
        if self.system:self.system.stopSpeakingAtBoundary(0)
