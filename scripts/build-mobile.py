"""Rebuild mobile resources in the required order; never signs or publishes remotely."""
import argparse
from pathlib import Path
import subprocess
import sys
import os
import json
import shutil
import hashlib
ROOT=Path(__file__).resolve().parent.parent
MOBILE=ROOT/'weizhuo/mobile'

def commands(platform,create=False,package=False):
    result=[([sys.executable,str(ROOT/'scripts/versioning.py'),'--sync'],ROOT),
            ([sys.executable,'prepare.py'],MOBILE),
            ([sys.executable,'-m','briefcase','create' if create else 'update',platform],MOBILE),
            ([sys.executable,'configure_ios.py' if platform=='iOS' else 'configure_android.py'],MOBILE),
            ([sys.executable,'-m','briefcase','build',platform],MOBILE)]
    if package:
        if platform!='android':raise ValueError('iPhone exports require an explicit signing/distribution choice in Xcode')
        result.append(([sys.executable,'-m','briefcase','package','android','-p','debug-apk'],MOBILE))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform',choices=('iOS','android'))
    parser.add_argument('--create',action='store_true',help='Create a new platform project instead of updating one.')
    parser.add_argument('--debug-apk',action='store_true',help='Package an Android test APK after building.')
    parser.add_argument('--plan',action='store_true',help='Print the build sequence without modifying files.')
    parser.add_argument('--release-apk',action='store_true',help='Build an optimized ARM64 phone APK, locally signed with the existing test key.')
    parser.add_argument('--emulator',action='store_true',help='Build a separate x86_64 emulator package, never a universal APK.')
    args=parser.parse_args()
    if args.release_apk and (args.platform!='android' or args.debug_apk):parser.error('--release-apk requires android and excludes --debug-apk')
    if args.emulator and args.platform!='android':parser.error('--emulator requires android')
    try:steps=commands(args.platform,args.create,args.debug_apk)
    except ValueError as error:parser.error(str(error))
    if args.platform=='android':
        arch='x86_64' if args.emulator else 'arm64-v8a'
        steps[3][0].extend(['--arch',arch])
    if args.release_apk:
        steps=steps[:-1]
        steps.append(([str(MOBILE/'build/weizhuomobile/android/gradle/gradlew'),'assembleRelease','-PweizhuoLocalSigning=true','--console=plain'],MOBILE/'build/weizhuomobile/android/gradle'))
    for command,directory in steps:
        print(f'{directory.relative_to(ROOT) or "."}: '+' '.join(command),flush=True)
        if not args.plan:
            env=os.environ.copy()
            if args.platform=='android':
                env.setdefault('JAVA_HOME',str(Path.home()/'Library/Caches/org.beeware.briefcase/tools/java17/Contents/Home'))
                env.setdefault('ANDROID_HOME',str(Path.home()/'Library/Caches/org.beeware.briefcase/tools/android_sdk'))
            completed=subprocess.run(command,cwd=directory,env=env)
            if completed.returncode:return completed.returncode
    if args.release_apk and not args.plan:
        identity=json.loads((ROOT/'version.json').read_text())
        release=identity['version']+('.'+identity['prerelease'] if identity.get('prerelease') else '-build'+str(identity['build']))
        label='android-emulator-x86_64' if args.emulator else 'android-arm64'
        output=ROOT/'dist'/release/label
        output.mkdir(parents=True,exist_ok=True)
        target=output/f'weizhuo-{release}-{label}-release.apk'
        shutil.copy2(MOBILE/'build/weizhuomobile/android/gradle/app/build/outputs/apk/release/app-release.apk',target)
        (output/(target.name+'.sha256')).write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
        (output/'build-info.json').write_text(json.dumps({**identity,'platform':'android','arch':arch,'configuration':'Release','signing':'local existing test key'},indent=2)+'\n')
        print(target)
    return 0
if __name__=='__main__':sys.exit(main())
