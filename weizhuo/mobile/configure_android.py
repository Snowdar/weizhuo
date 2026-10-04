"""Apply canonical version to generated Gradle projects after create/update."""
from pathlib import Path
import json
import re
import shutil
import argparse


def configure_branding(app):
    """Replace template artwork after every Briefcase create/update."""
    from PIL import Image
    res = app / "src/main/res"
    source = ROOT / "src/weizhuomobile/runtime/static/assets/weizhuo-logo.png"
    with Image.open(source) as raw:
        logo = raw.convert("RGBA")
        for folder in res.glob("mipmap-*"):
            for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png", "splash.png"):
                target = folder / name
                if not target.exists():
                    continue
                with Image.open(target) as existing:
                    size = existing.size
                foreground = name == "ic_launcher_foreground.png"
                canvas = Image.new("RGBA", size, (0, 0, 0, 0) if foreground else "#fffdf3")
                inset = 0.58 if foreground else 0.80
                mark = logo.copy()
                mark.thumbnail((round(size[0] * inset), round(size[1] * inset)), Image.Resampling.LANCZOS)
                canvas.alpha_composite(mark, ((size[0] - mark.width) // 2, (size[1] - mark.height) // 2))
                canvas.save(target)
    (res / "values/colors.xml").write_text(
        '<resources><color name="colorPrimary">#244f3e</color>'
        '<color name="colorPrimaryDark">#244f3e</color>'
        '<color name="colorAccent">#dfbb77</color>'
        '<color name="colorSplashScreenBackground">#fffdf3</color></resources>\n')
    # Android 12+ supplies its own launch screen: explicitly brand that path too.
    folder = res / "values-v31"
    folder.mkdir(exist_ok=True)
    (folder / "styles.xml").write_text(
        '<resources><style name="AppTheme.Launcher">'
        '<item name="android:windowBackground">@drawable/splash_screen_background</item>'
        '<item name="android:windowSplashScreenBackground">@color/colorSplashScreenBackground</item>'
        '<item name="android:windowSplashScreenAnimatedIcon">@mipmap/ic_launcher_foreground</item>'
        '<item name="android:windowSplashScreenIconBackgroundColor">@color/colorSplashScreenBackground</item>'
        '</style></resources>\n')
    print("已应用围桌安卓图标、启动主题和 Android 12+ 系统启动图标。")

ROOT = Path(__file__).resolve().parent

def configure(path, identity):
    text = path.read_text()
    text, codes = re.subn(r'(?m)^(\s*versionCode\s*(?:=\s*)?)\d+', lambda m: m[1] + str(identity['build']), text)
    text, names = re.subn(r'(?m)^(\s*versionName\s*(?:=\s*)?)["\'][^"\']*["\']', lambda m: m[1] + json.dumps(identity['version'] + ('.' + identity['prerelease'] if identity.get('prerelease') else '')), text)
    if codes != 1 or names != 1:
        raise RuntimeError('Cannot locate unique Android versionCode/versionName')
    path.write_text(text)

def configure_arch(path, arch='arm64-v8a'):
    if arch not in ('arm64-v8a', 'x86_64'):
        raise ValueError('Phone and emulator builds must use a single supported ABI')
    text = path.read_text()
    text, count = re.subn(r'(?m)^\s*abiFilters[^\n]+', lambda m: '            abiFilters ' + json.dumps(arch), text)
    if count != 1:
        raise RuntimeError('Cannot locate unique Android abiFilters')
    path.write_text(text)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--arch',choices=('arm64-v8a','x86_64'),default='arm64-v8a')
    args=parser.parse_args()
    identity = json.loads((ROOT.parents[1] / 'version.json').read_text())
    folder = ROOT / 'build/weizhuomobile/android/gradle/app'
    path = next((p for p in (folder / 'build.gradle', folder / 'build.gradle.kts') if p.exists()), None)
    if path is None:
        raise RuntimeError('先运行 briefcase create android')
    configure(path, identity)
    configure_arch(path, args.arch)
    configure_branding(folder)
    java=folder/'src/main/java/com/snowdar/weizhuomobile'
    java.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'android/WeizhuoSpeaker.java',java/'WeizhuoSpeaker.java')
    assets=ROOT/'.voice-assets'
    aar=assets/'android/sherpa-onnx-1.13.8.aar'
    if not aar.exists():raise RuntimeError('先准备官方 sherpa-onnx 安卓运行库')
    libs=folder/'libs';libs.mkdir(exist_ok=True);shutil.copy2(aar,libs/aar.name)
    text=path.read_text()
    if 'sherpa-onnx-1.13.8.aar' not in text:
        text += '\ndependencies { implementation files("libs/sherpa-onnx-1.13.8.aar"); implementation "org.jetbrains.kotlin:kotlin-stdlib:2.1.0" }\n'
        path.write_text(text)
    if 'weizhuoLocalSigning' not in path.read_text():
        with path.open('a') as stream:
            stream.write('\n// Local test distribution only; public releases supply their own signing key.\nif (project.hasProperty("weizhuoLocalSigning")) { android.buildTypes.release.signingConfig = android.signingConfigs.debug }\n')
    voice=folder/'src/main/assets/Voice'
    if voice.exists():shutil.rmtree(voice)
    shutil.copytree(assets/'Voice',voice,ignore=shutil.ignore_patterns('model-fp16.onnx','*.previous','*-raw.wav','*-take*.wav','audio-review.json','review-evidence.json','quality-report.json','audit-report.json'))
    if (assets/'Voice/model-fp16.onnx').exists():shutil.copy2(assets/'Voice/model-fp16.onnx',voice/'model.onnx')
    print(f'Android {identity["version"]} (build {identity["build"]})')
