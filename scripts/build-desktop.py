"""Build on the target OS: python scripts/build-desktop.py (PyInstaller required)."""
from pathlib import Path
import platform
import hashlib
import urllib.request
import shutil
import subprocess
import sys
import argparse
import json
import plistlib
from versioning import release_identity

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'weizhuo'
DIST = ROOT / 'dist'
IDENTITY = release_identity()
VERSION = IDENTITY["version"]
BUILD = IDENTITY["build"]
RELEASE = VERSION + ("." + IDENTITY["prerelease"] if IDENTITY.get("prerelease") else "-build" + str(BUILD))
DISPLAY_NAME = '围桌'

def main():
    global DIST
    parser = argparse.ArgumentParser()
    parser.add_argument('--arch', choices=('arm64', 'x86_64'), default=None)
    args = parser.parse_args()
    actual = platform.machine().lower()
    arch = {'amd64': 'x86_64', 'aarch64': 'arm64'}.get(actual, actual)
    if args.arch and args.arch != arch:
        raise RuntimeError(f'构建 Python 架构是 {arch}，不能标成 {args.arch}；请使用对应架构的 Python。')
    system = {'darwin': 'macos', 'win32': 'windows'}.get(sys.platform, sys.platform)
    DIST = DIST / RELEASE / f'{system}-{arch}'
    DIST.mkdir(parents=True, exist_ok=True)
    windows_version = DIST / 'windows-version.txt'
    parts = tuple(map(int, VERSION.split('.'))) + (BUILD,)
    windows_version.write_text("VSVersionInfo(ffi=FixedFileInfo(filevers=" + repr(parts) + ", prodvers=" + repr(parts) + ", mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription','围桌'), StringStruct('ProductName','围桌'), StringStruct('FileVersion', '" + VERSION + "." + str(BUILD) + "'), StringStruct('ProductVersion','" + RELEASE + "')])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])", encoding='utf-8')
    if sys.platform == 'darwin':
        import tkinter
        tk = tkinter.Tcl()
        tk.eval('package require Tk')
        version = tk.eval('package provide Tk')
        tk.eval('destroy .')
        if tuple(int(x) for x in version.split('.')[:3]) < (8, 6, 13):
            raise RuntimeError('Mac 打包需要 Tk 8.6.13 或以上；旧版存在退出时窗口释放崩溃。')
    voice=APP/'mobile/.voice-assets/Voice'
    if not (voice/'model.onnx').exists() or not (voice/'Serena/manifest.json').exists():raise RuntimeError('桌面四音色构建需要本地 Voice 模型及已采纳 Serena 素材；见构建说明')
    import sherpa_onnx
    from importlib.metadata import version
    if version('sherpa-onnx')!='1.13.8':raise RuntimeError('请安装 sherpa-onnx==1.13.8')
    from sys import path
    path.insert(0,str(APP/'mobile'))
    from serena_quality import verify_library
    verify_library(voice/'Serena')
    staged=DIST/'voice-resources'
    if staged.exists():shutil.rmtree(staged)
    shutil.copytree(voice,staged,ignore=shutil.ignore_patterns('model-fp16.onnx','*.previous','*-raw.wav','*-take*.wav','audio-review.json','review-evidence.json','quality-report.json','audit-report.json'))
    if (voice/'model-fp16.onnx').exists():shutil.copy2(voice/'model-fp16.onnx',staged/'model.onnx')
    subprocess.run([sys.executable, '-m', 'PyInstaller' , '--noconfirm', '--clean', '--windowed', '--name', DISPLAY_NAME,
        '--distpath', str(DIST), '--workpath', str(ROOT / 'build'), '--specpath', str(ROOT / 'build'),
        *(['--version-file', str(windows_version)] if sys.platform == 'win32' else []),
        *(['--target-architecture', arch] if sys.platform == 'darwin' else []),
        '--collect-all', 'sherpa_onnx',  '--add-data', f'{staged}:Voice',
        '--exclude-module', 'PIL', '--paths', str(APP), '--paths', str(APP / 'vendor'),
        '--add-data', f'{APP / "static"}:static', '--add-data', f'{APP / "vendor"}:vendor',
        '--icon', str(APP / 'static/assets/weizhuo-logo.png'),
        '--osx-bundle-identifier', 'com.snowdar.weizhuo', str(APP / 'desktop/launcher.py')], check=True)
    binary = DIST / (f'{DISPLAY_NAME}.app/Contents/MacOS/{DISPLAY_NAME}' if sys.platform == 'darwin' else f'{DISPLAY_NAME}/{DISPLAY_NAME}.exe' if sys.platform == 'win32' else f'{DISPLAY_NAME}/{DISPLAY_NAME}')
    report = DIST / 'smoke-report.json'
    subprocess.run([str(binary), '--self-test-report', str(report)], check=True, timeout=60)
    if '"ok": true' not in report.read_text():
        raise RuntimeError('打包自检未通过')
    bundle = DIST / (f'{DISPLAY_NAME}.app' if sys.platform == 'darwin' else DISPLAY_NAME)
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT / name, bundle / 'Contents' / 'Resources' / name if sys.platform == 'darwin' else bundle / name)
    notices = bundle / 'Contents' / 'Resources' / 'licenses' if sys.platform == 'darwin' else bundle / 'licenses'
    notices.mkdir(parents=True, exist_ok=True)
    license_sources = {
        'Python.txt': f'https://raw.githubusercontent.com/python/cpython/{sys.version_info.major}.{sys.version_info.minor}/LICENSE',
        'Tcl.txt': 'https://raw.githubusercontent.com/tcltk/tcl/core-8-6-branch/license.terms',
        'Tk.txt': 'https://raw.githubusercontent.com/tcltk/tk/core-8-6-branch/license.terms',
        'PyInstaller.txt': 'https://raw.githubusercontent.com/pyinstaller/pyinstaller/v6.16.0/COPYING.txt',
    }
    for name, url in license_sources.items():
        with urllib.request.urlopen(url, timeout=30) as response:
            (notices / name).write_bytes(response.read())
    resources = bundle / 'Contents/Resources' if sys.platform == 'darwin' else bundle
    metadata = {**IDENTITY, 'platform': system, 'arch': arch, 'self_test': 'passed', 'configuration': 'Release'}
    (resources / 'build-info.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    (DIST / 'build-info.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if sys.platform == 'darwin':
        plist = bundle / 'Contents/Info.plist'
        info = plistlib.loads(plist.read_bytes())
        info.update(CFBundleShortVersionString=VERSION, CFBundleVersion=str(BUILD))
        plist.write_bytes(plistlib.dumps(info))
        subprocess.run(['codesign' , '--force', '--deep', '--sign', '-', str(bundle)], check=True)
    asset = DIST / f'weizhuo-{RELEASE}-{system}-{arch}'
    if sys.platform == 'darwin':
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(bundle), str(asset) + '.zip'], check=True)
    else:
        shutil.make_archive(str(asset), 'zip', DIST, bundle.name)
    archive = Path(str(asset) + '.zip')
    (DIST / (archive.name + '.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    # Keep unpacked build products out of Spotlight/App searches.
    if sys.platform == 'darwin':
        unpacked=DIST/'bundles.noindex'
        unpacked.mkdir(exist_ok=True)
        if (unpacked/bundle.name).exists():shutil.rmtree(unpacked/bundle.name)
        shutil.move(str(bundle),unpacked/bundle.name)
    print(archive)

if __name__ == '__main__':
    main()
