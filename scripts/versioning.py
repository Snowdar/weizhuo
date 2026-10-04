"""One release identity shared by native packages. No publishing side effects."""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

def release_identity():
    value = json.loads((ROOT / "version.json").read_text())
    if not re.fullmatch(r"\d+\.\d+\.\d+", value["version"]):
        raise ValueError("version must be major.minor.patch")
    if type(value["build"]) is not int or not 1 <= value["build"] < 65536:
        raise ValueError("build must be an integer from 1 to 65535")
    if value.get("prerelease") is not None and not re.fullmatch(r"a[1-9]\d*", value["prerelease"]):
        raise ValueError("prerelease must be a positive alpha label, such as a1")
    return value

def mobile_config(identity):
    path = ROOT / "weizhuo/mobile/pyproject.toml"
    text = path.read_text()
    text = re.sub(r'^version = ".*"$', f'version = "{identity["version"]}"', text, count=1, flags=re.M)
    text = re.sub(r'^build = \d+\n', '', text, flags=re.M)
    text = text.replace('[tool.briefcase.app.weizhuomobile]\n', f'[tool.briefcase.app.weizhuomobile]\nbuild = {identity["build"]}\n')
    text = re.sub(r'^version_code = \d+\n', '', text, flags=re.M)
    text = text.replace('[tool.briefcase.app.weizhuomobile.android]\n', f'[tool.briefcase.app.weizhuomobile.android]\nversion_code = {identity["build"]}\n')
    return path, text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sync', action='store_true', help='update native configuration from version.json')
    args = parser.parse_args()
    identity = release_identity()
    path, expected = mobile_config(identity)
    if args.sync:
        path.write_text(expected)
    elif path.read_text() != expected:
        print('移动版本配置不一致；运行 python scripts/versioning.py --sync', file=sys.stderr)
        return 1
    print(f'围桌 {identity["version"]} (build {identity["build"]})')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
