"""Reject stale embedded web/server resources before signing a mobile package."""
import hashlib
import json
from pathlib import Path

APP=Path(__file__).resolve().parents[1]

def assert_runtime_current(runtime,source=APP):
    runtime=Path(runtime);source=Path(source)
    expected=[source/'server.py']
    for folder in ('static','scoring','vendor'):
        expected.extend(p for p in (source/folder).rglob('*') if p.is_file() and not {'__pycache__','tests','screenshots'}.intersection(p.relative_to(source).parts) and p.suffix!='.pyc')
    stale=[]
    for path in expected:
        relative=path.relative_to(source);target=runtime/relative
        if not target.is_file() or hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256(target.read_bytes()).digest():
            stale.append(str(relative))
    identity=source.parent/'version.json'
    if json.loads((runtime/'resources/build-info.json').read_text())!=json.loads(identity.read_text()):stale.append('resources/build-info.json')
    if stale:
        raise RuntimeError('移动运行资源过期：'+', '.join(stale[:6])+'。先运行 prepare.py，再 briefcase update 平台；禁止签署旧页面。')
