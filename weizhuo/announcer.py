"""Desktop-local VITS and Serena synthesis; no network or mutable game state."""
from pathlib import Path
import io
import threading
import wave
from mobile.src.weizhuomobile.speech import SerenaClips, announcer_text

class LocalAnnouncer:
    def __init__(self, base):
        self.base=Path(base)
        self.clips=SerenaClips(self.base/'Serena')
        self.engine=None
        self.lock=threading.Lock()
        self.choices=[0]+([1,2] if (self.base/'model.onnx').is_file() else [])+([3] if self.clips.recipes or self.clips.segments or self.clips.clips else [])

    def render(self, text, voice):
        if not isinstance(text,str) or not 0<len(text)<=1000:raise ValueError('播报文字长度不正确')
        if not isinstance(voice,int) or isinstance(voice,bool) or voice not in self.choices or voice==0:raise ValueError('请选择已配置的离线音色')
        text=announcer_text(text)
        # Serialize inference; reject excess concurrent requests instead of accumulating.
        if not self.lock.acquire(blocking=False):raise ValueError('上一条播报尚在合成，请稍后重试')
        try:
            output=io.BytesIO()
            if voice==3:
                paths=self.clips.plan(text)
                if not paths:raise ValueError('暖语暂未覆盖本句，请查看文字记录')
                rate=None;frames=[]
                for path in paths:
                    with wave.open(str(path),'rb') as wav:
                        if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getcomptype()!='NONE':raise ValueError('暖语片段格式不正确')
                        if rate is not None and rate!=wav.getframerate():raise ValueError('暖语片段采样率不一致')
                        rate=wav.getframerate();frames.append(wav.readframes(wav.getnframes()))
                with wave.open(output,'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate);wav.writeframes(b''.join(frames))
            else:
                import sherpa_onnx
                import numpy as np
                if self.engine is None:
                    model=self.base/'model-fp16.onnx'
                    if not model.exists():model=self.base/'model.onnx'
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(model),lexicon=str(self.base/'lexicon.txt'),tokens=str(self.base/'tokens.txt'),dict_dir=str(self.base/'dict'),noise_scale=.667,noise_scale_w=.8,length_scale=1)
                    config=sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(vits=vits,num_threads=4,provider='cpu'),rule_fsts=str(self.base/'number.fst'),max_num_sentences=1,silence_scale=.2)
                    self.engine=sherpa_onnx.OfflineTts(config)
                config=sherpa_onnx.GenerationConfig();config.sid=voice;config.speed=1.0;config.silence_scale=.2
                audio=self.engine.generate(text,config)
                pcm=(np.clip(audio.samples,-1,1)*32767).astype('<i2').tobytes()
                with wave.open(output,'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(audio.sample_rate);wav.writeframes(pcm)
            return output.getvalue()
        finally:self.lock.release()
