"""Explicit developer download, verified against pinned asset digests."""
from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
import argparse
ROOT=Path(__file__).resolve().parent

def provision(platform="ios"):
    assets=ROOT/".voice-assets";assets.mkdir(exist_ok=True)
    bundled=ROOT.parent.parent/'resources/voice'
    if bundled.is_dir() and not (assets/'Voice').exists():
        inventory=json.loads((bundled/'files.sha256.json').read_text())
        for name,spec in inventory.items():
            source=bundled/name
            if not source.resolve().is_relative_to(bundled.resolve()) or source.is_symlink():
                raise RuntimeError('随仓库语音资源路径不安全')
            if source.stat().st_size!=spec['bytes'] or hashlib.sha256(source.read_bytes()).hexdigest()!=spec['sha256']:
                raise RuntimeError('随仓库语音资源校验失败')
        shutil.copytree(bundled,assets/'Voice')
        print('已使用仓库内 FP16 VITS 与正式 Serena；无需下载或重新合成音色。')
    manifest=json.loads((ROOT/'ios/voice/assets.json').read_text())
    selected={name:spec for name,spec in manifest.items() if (name=='model' and not (assets/'Voice/model.onnx').exists()) or (name=='framework' and platform=='ios' and not (assets/'SherpaOnnxC.xcframework').exists())}
    if platform=='android':selected['android']={'url':'https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-1.13.8.aar','sha256':'633c24321e06b1fe79feafa03ea16cbc0f8a286641e2da3559bac91bdb13bd96'}
    with tempfile.TemporaryDirectory() as temporary:
        work=Path(temporary)
        for name,spec in selected.items():
            archive=work/name
            print(f'下载 {name}……')
            with urllib.request.urlopen(spec['url'],timeout=60) as response,archive.open('wb') as output:
                shutil.copyfileobj(response,output)
            if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()!=spec['sha256']:
                raise RuntimeError(f'{name} 校验失败；不安装资源')
            if name=='android':
                dest=assets/'android';dest.mkdir(exist_ok=True);shutil.copy2(archive,dest/'sherpa-onnx-1.13.8.aar');continue
            dest=work/(name+'-unpacked');dest.mkdir()
            if name=='model':
                with tarfile.open(archive) as bundle:
                    for member in bundle.getmembers():
                        if member.issym() or member.islnk() or not (dest/member.name).resolve().is_relative_to(dest.resolve()):
                            raise RuntimeError('模型包包含不安全路径')
                    bundle.extractall(dest,filter='data')
            else:
                with zipfile.ZipFile(archive) as bundle:
                    for item in bundle.namelist():
                        if not (dest/item).resolve().is_relative_to(dest.resolve()):raise RuntimeError('框架包含不安全路径')
                    bundle.extractall(dest)
        assets=ROOT/'.voice-assets';assets.mkdir(exist_ok=True)
        for name in ('model','framework'):
            if name not in selected:continue
            source=next((work/(name+'-unpacked')).rglob('model.onnx')).parent if name=='model' else next((work/(name+'-unpacked')).rglob('SherpaOnnxC.xcframework'))
            target=assets/('Voice' if name=='model' else 'SherpaOnnxC.xcframework')
            if target.exists():raise RuntimeError('资源已存在，不覆盖已采纳音色')
            shutil.copytree(source,target)
        print('资源已就绪；运行 configure_ios.py 配置本地构建。')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--platform',choices=('ios','android','desktop'),default='ios')
    provision(parser.parse_args().platform)
