#!/usr/bin/env python3
"""Compose nine actual screenshots; requires Pillow and a CJK font."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('screenshots',type=Path,help='Directory containing 01-launch.png through 09-records.jpg')
p.add_argument('--output',type=Path,default=Path('docs/media/mobile-nine-grid.jpg'))
p.add_argument('--font',default='/System/Library/Fonts/STHeiti Medium.ttc')
a=p.parse_args()
titles=['启动主题','服务首页','游戏大厅','自由积分 · 简约','自由积分 · 牌桌','炸金花','德州扑克','规则与收藏','记分记录']
files=['01-launch.png','02-service.png','03-hall.jpg','04-free-simple.jpg','05-free-table.jpg','06-zhajinhua.jpg','07-holdem.jpg','08-rules.jpg','09-records.jpg']
w,h,gap,margin=393,852,24,32
heading,caption=100,58
canvas=Image.new('RGB',(margin*2+3*w+2*gap,heading+margin+3*(h+caption)+2*gap+margin),'#f3f1e7')
draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype(a.font,34);small=ImageFont.truetype(a.font,23)
draw.text((margin,22),'围桌 · 手机界面一览',font=font,fill='#214b3d')
draw.text((margin,67),'线下游戏，线上记分 · 仅需局域网，无需互联网',font=small,fill='#6e7f70')
for i,(file,title) in enumerate(zip(files,titles)):
 im=Image.open(a.screenshots/file).convert('RGB')
 if i==1:
  # Hide the simulator host's real LAN address in the published screenshot.
  box=(int(im.width*.07),int(im.height*.55),int(im.width*.90),int(im.height*.60))
  im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(24)),box)
 im=im.resize((w,h),Image.Resampling.LANCZOS)
 x=margin+(i%3)*(w+gap);y=heading+margin+(i//3)*(h+caption+gap)
 draw.text((x,y),f'{i+1:02d}  {title}',font=small,fill='#214b3d')
 canvas.paste(im,(x,y+caption))
 draw.rectangle((x-1,y+caption-1,x+w,y+caption+h),outline='#d8dece',width=1)
a.output.parent.mkdir(parents=True,exist_ok=True)
canvas.save(a.output,quality=90,optimize=True,progressive=True)
print(a.output,canvas.size,a.output.stat().st_size)
