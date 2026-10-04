"""Embed locally provisioned voice assets; never fetch models during App use."""
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parent

def configure(project):
    assets=ROOT/'.voice-assets'
    if not (assets/'Voice/model.onnx').exists() or not (assets/'SherpaOnnxC.xcframework').exists():
        print('未配置本地神经音色资源；iOS 保留系统离线播报。')
        return
    serena=assets/'Voice/Serena'
    if (serena/'manifest.json').exists():
        from serena_quality import verify_library
        print(f'Serena 素材门槛检查通过：{verify_library(serena)} 条。')
    native=project.parent/'Support'
    for name in ('Voice','SherpaOnnxC.xcframework'):
        dest=native/name
        if dest.exists():shutil.rmtree(dest)
        shutil.copytree(assets/name,dest,ignore=shutil.ignore_patterns('model-fp16.onnx','*.previous','*-raw.wav','*-take*.wav','audio-review.json','review-evidence.json','quality-report.json','audit-report.json'))
        if name=='Voice' and (assets/'Voice/model-fp16.onnx').exists():
            shutil.copy2(assets/'Voice/model-fp16.onnx',dest/'model.onnx')
    shutil.copy2(ROOT/'ios/voice/WZOfflineSpeaker.mm',native/'WZOfflineSpeaker.mm')
    path=project/'project.pbxproj';text=path.read_text()
    if 'WZOfflineSpeaker.mm in Sources' not in text:
        def entry(section,value):
            nonlocal text
            text=text.replace(f'/* End {section} section */',value+'\n'+f'/* End {section} section */')
        for ident,ref,settings in [('A1','B1','settings = {COMPILER_FLAGS = "-fobjc-arc"; };'),('A2','B2',''),('A3','B2','settings = {ATTRIBUTES = (CodeSignOnCopy, RemoveHeadersOnCopy, ); };'),('A4','B3','')]:
            entry('PBXBuildFile',f'        ABCD000000000000000000{ident} = {{isa = PBXBuildFile; fileRef = ABCD000000000000000000{ref}; {settings}}};')
        for ident,name,kind in [('B1','WZOfflineSpeaker.mm','sourcecode.cpp.objcpp'),('B2','SherpaOnnxC.xcframework','wrapper.xcframework'),('B3','Voice','folder')]:
            entry('PBXFileReference',f'        ABCD000000000000000000{ident} = {{isa = PBXFileReference; lastKnownFileType = {kind}; path = "Support/{name}"; sourceTree = SOURCE_ROOT; }};')
        for phase,ident in [('PBXSourcesBuildPhase','A1'),('PBXFrameworksBuildPhase','A2'),('PBXCopyFilesBuildPhase','A3'),('PBXResourcesBuildPhase','A4')]:
            pattern=rf'(isa = {phase};.*?files = \()'
            text=re.sub(pattern,rf'\1\n                ABCD000000000000000000{ident},',text,count=1,flags=re.S)
        # Named marker permits safe idempotent configuration after Briefcase updates.
        text=text.replace('ABCD000000000000000000A1 =','ABCD000000000000000000A1 /* WZOfflineSpeaker.mm in Sources */ =')
    if 'AVFoundation' not in text:
        text=text.replace('WRAPPER_EXTENSION = app;', 'OTHER_LDFLAGS = "$(inherited) -framework AVFoundation";\n                WRAPPER_EXTENSION = app;')
    path.write_text(text)
    print('已嵌入离线男女音色；语速 1.0 倍。')
