"""Collect only app resources; never package local rooms, tokens or test data."""
from pathlib import Path
import shutil
import json
from PIL import Image
APP=Path(__file__).resolve().parents[1]
DEST=Path(__file__).resolve().parent/'src/weizhuomobile/runtime'
def prepare():
    if DEST.exists():shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (DEST/'__init__.py').write_text('')
    for name in ('scoring','vendor','static'):
        shutil.copytree(APP/name,DEST/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','tests','screenshots'))
    shutil.copy2(APP/'server.py',DEST/'server.py')
    # Platform icon sizes are derived from the existing project artwork.
    icons=DEST/'resources'
    icons.mkdir()
    identity=json.loads((APP.parent/"version.json").read_text())
    (icons/"build-info.json").write_text(json.dumps(identity,indent=2)+"\n")
    with Image.open(APP/'static/assets/weizhuo-logo.png') as source:
        image=Image.new('RGB',source.size,'#fffdf3')
        image.paste(source,mask=source.getchannel('A') if source.mode=='RGBA' else None)
        for size in (20,29,40,58,60,76,80,87,120,152,167,180,640,1024,1280,1920):
            image.resize((size,size),Image.Resampling.LANCZOS).save(icons/f'app-icon-{size}.png')
    with Image.open(APP/'static/assets/service-launch-poster-v2.webp') as poster:
        for size in (640,1280,1920):
            poster.resize((size,size*3//2),Image.Resampling.LANCZOS).save(icons/f'splash-{size}.png')
    with Image.open(APP/'static/assets/service-home-background-v2.webp') as background:
        background.thumbnail((768,1152),Image.Resampling.LANCZOS)
        background.convert('RGB').save(icons/'service-background.jpg',quality=82,optimize=True)
    print('已收集运行代码、网页与素材；不包含数据库、测试房间或私人身份。')
if __name__=='__main__':prepare()
