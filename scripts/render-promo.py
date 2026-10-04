"""Render a short promo from real paired UI captures, native intro and app WAVs.
Usage: python scripts/render-promo.py CAPTURE_DIRECTORY --native-intro FILE
edit.json: ordered {label,duration,kind,frames:[{left,right?,at}],voices:[{file,text,offset}]}
kind native requires sourceStart; still/paired uses actual screenshot paths. No TTS or UI fabrication.
"""
import argparse,json,subprocess,wave,re
from pathlib import Path
import numpy as np
from scipy.io import wavfile
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--native-intro',type=Path,required=True);a=p.parse_args();P=a.directory.resolve()
edit=json.loads((P/'edit.json').read_text());narr=json.loads((P/'narration.json').read_text());FONT='/System/Library/Fonts/STHeiti Medium.ttc';W,H=1280,1510

def run(args):subprocess.run(['ffmpeg','-y','-loglevel','error',*args],check=True)
def label(t,x,y,size=26):return f"drawtext=fontfile={FONT}:text='{t}':fontsize={size}:fontcolor=0x244a3b:x={x}:y={y}"
enc=['-r','30','-an','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p']
clips=[];subs=[];cursor=0;audio=[]
for i,e in enumerate(edit):
 d=e['duration'];dest=P/f'edit-{i}.mp4';kind=e['kind'];title=e.get('title','')
 if kind=='native':
  vf='scale=600:1300:force_original_aspect_ratio=decrease,pad=1280:1510:(ow-iw)/2:90:color=0xf5f4e9,'+label(title,'(w-tw)/2',36)
  run(['-ss',str(e['sourceStart']),'-i',str(a.native_intro),'-t',str(d),'-vf','setpts=PTS-STARTPTS,'+vf+f',fps=30,tpad=stop_mode=clone:stop_duration={d}',*enc,str(dest)])
 elif kind=='still':
  vf='scale=600:1300:force_original_aspect_ratio=decrease,pad=1280:1510:(ow-iw)/2:90:color=0xf5f4e9,'+label(title,'(w-tw)/2',36)
  run(['-loop','1','-i',e['frames'][0]['left'],'-t',str(d),'-vf',vf,*enc,str(dest)])
 else:
  shots=e['frames'];inputs=[]
  for key in ['left','right']:
   fc=P/f'edit-{i}-{key}.txt';lines=['ffconcat version 1.0']
   for j,f in enumerate(shots):
    delta=(shots[j+1]['at']-f['at'])/1000 if j+1<len(shots) else max(.05,d-(f['at']-shots[0]['at'])/1000)
    lines += [f"file '{f[key]}'",f'duration {max(.001,delta):.6f}']
   lines.append(lines[-2]);fc.write_text('\n'.join(lines)+'\n');inputs += ['-safe','0','-f','concat','-i',str(fc)]
  filters="[0:v]scale=600:1300,setsar=1[l];[1:v]scale=600:1300,setsar=1[r];color=c=0xf5f4e9:s=1280x1510:r=30[b];[b][l]overlay=24:90[x];[x][r]overlay=656:90,"+label('1 号玩家 · 小林 · 房主全屏',24,35)+','+label('2 号玩家 · 小夏 · 普通视图',656,35)+','+label(title,'(w-tw)/2',1396,22)+'[v]'
  run([*inputs,'-filter_complex',filters,'-map','[v]','-t',str(d),*enc,str(dest)])
 if e.get('narration'):audio.append((P/(e['narration']+'.wav'),cursor+.2,narr[e['narration']]))
 for v in e.get('voices',[]):audio.append((P/v['file'],cursor+v['offset'],v['text'].replace('全下','All-in')))
 measured=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(dest)],text=True))
 if abs(measured-d)>.06:raise RuntimeError(f'Clip duration mismatch: {e["label"]} {measured} != {d}')
 clips.append(dest);e['start']=cursor;cursor+=d
 print(e['label'],d,flush=True)
(P/'promo-clips.txt').write_text('\n'.join(f"file '{c}'" for c in clips));run(['-safe','0','-f','concat','-i',str(P/'promo-clips.txt'),'-c','copy',str(P/'silent.mp4')])
rate=24000;mix=np.zeros(round(cursor*rate),np.float32);lastEnd=0
for file,at,text in sorted(audio,key=lambda x:x[1]):
 sr,pcm=wavfile.read(file);assert sr==rate;pcm=pcm.astype(np.float32)/32768;assert at>=lastEnd-.02,'Overlapping speech';lastEnd=at+len(pcm)/sr;assert lastEnd<=cursor
 idx=round(at*rate);mix[idx:idx+len(pcm)]+=pcm*.9;subs.append((at,lastEnd,text))
assert np.max(np.abs(mix))<1;wavfile.write(P/'mixed.wav',rate,(mix*32767).astype(np.int16))
def stamp(s):
 c=round(s*100);return f'{c//360000}:{c//6000%60:02}:{c//100%60:02}.{c%100:02}'
ass=['[Script Info]','ScriptType: v4.00+','PlayResX: 1280','PlayResY: 1510','WrapStyle: 2','[V4+ Styles]','Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding','Style: Default,Heiti SC,28,&H003B4A24,&H003B4A24,&H00F5F4E9,&H00F5F4E9,0,0,0,0,100,100,0,0,1,0,0,2,28,28,24,1','[Events]','Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text']
for start,end,text in subs:
 phrases=[x for x in re.split('(?<=[，。！？])',text) if x];total=sum(map(len,phrases));at=start
 for phrase in phrases:
  duration=(end-start)*len(phrase)/total;ass.append(f'Dialogue: 0,{stamp(at)},{stamp(at+duration)},Default,,0,0,0,,{phrase}');at+=duration
(P/'subtitles.ass').write_text('\n'.join(ass)+'\n');(P/'timeline.json').write_text(json.dumps(edit,ensure_ascii=False,indent=2))
run(['-i',str(P/'silent.mp4'),'-i',str(P/'mixed.wav'),'-vf',f"ass={P/'subtitles.ass'}:fontsdir=/System/Library/Fonts",'-t',str(cursor),'-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(P/'holdem-two-player.mp4')])
run(['-ss',str(cursor-9),'-i',str(P/'holdem-two-player.mp4'),'-frames:v','1','-pix_fmt','yuvj420p',str(P/'poster.jpg')]);print('Complete',cursor,'seconds;',len(audio),'speech clips')
