"""Install a reproducible Xcode scheme compatible with embedded SQLite."""
from pathlib import Path
import re
import json
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
from runtime_check import assert_runtime_current
assert_runtime_current(ROOT/'src/weizhuomobile/runtime')
assert_runtime_current(ROOT/'build/weizhuomobile/ios/xcode/围桌/app/weizhuomobile/runtime')
project=ROOT/'build/weizhuomobile/ios/xcode/围桌.xcodeproj'
text=(project/'project.pbxproj').read_text()
target=re.search(r'([A-F0-9]+) /\* 围桌 \*/ = \{\s*isa = PBXNativeTarget;',text)
if not target:raise RuntimeError('Cannot locate the 围桌 native target')
scheme=project/'xcshareddata/xcschemes/围桌.xcscheme'
tree=ET.parse(scheme if scheme.exists() else ROOT/'ios/围桌.xcscheme')
for ref in tree.findall('.//BuildableReference'):
    ref.set('BlueprintIdentifier',target[1])
tree.find('LaunchAction').set('disablePerformanceAntipatternChecker','YES')
scheme.parent.mkdir(parents=True,exist_ok=True)
tree.write(scheme,encoding='UTF-8',xml_declaration=True)
print('已配置 iOS SQLite 兼容调试；主线程 API 检查保持启用。')

# Keep launch artwork reproducible; never retain Briefcase's default bee.
app_dir=project.parent/'围桌'
shutil.copy2(ROOT/'ios/LaunchScreen.storyboard',app_dir/'Launch Screen.storyboard')
for size in (640,1280,1920):
    shutil.copy2(ROOT/f'src/weizhuomobile/runtime/resources/splash-{size}.png',app_dir/f'Images.xcassets/Splash.imageset/splash-{size}.png')
print('已应用围桌主题启动画面。')

# iOS 27 rejects an empty scene manifest. The project owns this adapter,
# keeping Toga and Rubicon packages unchanged.
import plistlib
plist=app_dir/'围桌-Info.plist'
with plist.open('rb') as stream:info=plistlib.load(stream)
identity=json.loads((ROOT.parents[1]/'version.json').read_text())
info['CFBundleShortVersionString']=identity['version']
info['CFBundleVersion']=str(identity['build'])
info['UIApplicationSceneManifest']={
    'UIApplicationSupportsMultipleScenes':False,
    'UISceneConfigurations':{'UIWindowSceneSessionRoleApplication':[{
        'UISceneConfigurationName':'围桌',
        'UISceneClassName':'UIWindowScene',
        'UISceneDelegateClassName':'WeizhuoSceneDelegate',
    }]},
}
with plist.open('wb') as stream:plistlib.dump(info,stream)
print('已配置 iOS 单窗口场景生命周期。')

from configure_voice import configure
configure(project)
