"""Check publishable source names and common secret markers without printing secrets.

Uses Git's file inventory (including untracked, non-ignored files by default).
Pass --staged to check the exact next commit. This is a guard, not a secret scanner guarantee.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PARTS = {'.voice-assets', '.voice-auditions', '.venv', '__pycache__', 'node_modules'}
FORBIDDEN_SUFFIXES = {'.db', '.sqlite3', '.log', '.pem', '.key', '.keystore', '.jks', '.mobileprovision', '.p12', '.ipa', '.apk', '.onnx', '.aar', '.pyc'}
MARKERS = {
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'access token': re.compile(rb'(?<![\w-])(?:ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{35,}|sk-[A-Za-z0-9]{25,})'),
    'personal macOS path': re.compile(rb'/' + rb'Users/[^/\s"<>]+/'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    command = ['git', 'ls-files', '-z', '--cached']
    if not args.staged:
        command += ['--others', '--exclude-standard']
    names = sorted(set(subprocess.check_output(command, cwd=ROOT).split(b'\0')) - {b''})
    inventory_path='resources/voice/files.sha256.json'
    inventory_raw=subprocess.check_output(['git','show',':'+inventory_path],cwd=ROOT) if args.staged else (ROOT/inventory_path).read_bytes()
    voice_inventory=json.loads(inventory_raw)
    problems = []
    count = 0
    for raw in names:
        name = raw.decode('utf-8')
        path = Path(name)
        local = ROOT / path
        if not args.staged and not local.exists():
            continue
        approved_voice = name.startswith("resources/voice/") and name.removeprefix("resources/voice/") in voice_inventory
        forbidden = (FORBIDDEN_PARTS.intersection(path.parts) or (path.suffix in FORBIDDEN_SUFFIXES and not approved_voice)
                     or (path.name.startswith('.env') and path.name != '.env.example')
                     or path.parts[0] in ('dist', 'build', 'backups'))
        if forbidden:
            problems.append((name, 'local/generated or private file'))
            continue
        if local.is_symlink():
            problems.append((name, 'symlink requires manual publication review'))
            continue
        data = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT) if args.staged else local.read_bytes()
        count += 1
        if approved_voice:
            spec=voice_inventory[name.removeprefix('resources/voice/')]
            if len(data)!=spec['bytes'] or hashlib.sha256(data).hexdigest()!=spec['sha256']:
                problems.append((name,'bundled voice checksum mismatch'))
        if len(data) > (99 if approved_voice else 20) * 1024 * 1024:
            problems.append((name, 'source file exceeds 20 MiB'))
        if b'\0' not in data[:8192]:
            for label, pattern in MARKERS.items():
                if pattern.search(data):
                    problems.append((name, label))
    for name, label in problems:
        print(f'{name}: {label}', file=sys.stderr)
    if problems:
        return 1
    print(f'Publishable source check passed: {count} files; no detected private/generated inputs or common secret markers.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
