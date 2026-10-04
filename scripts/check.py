"""Run regression suites without starting the live scoreboard."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "weizhuo"

def main():
    node = shutil.which("node")
    if not node:
        print("完整验证需要 Node.js；请安装后重试。", file=sys.stderr)
        return 1
    checks = [
        ([sys.executable, "scripts/versioning.py"], ROOT),
        ([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"], APP),
        ([node, "test_compare_dialog.cjs"], APP),
        ([node, "test_holdem_ui.cjs"], APP),
        ([node, "test_sound.cjs"], APP),
        ([node, "test_native_voice.cjs"], APP),
        ([node, "test_keyboard_layer.cjs"], APP),
    ]
    voice=APP / 'mobile/.voice-assets/Voice/Serena'
    if (voice / 'manifest.json').exists():
        checks.append(([sys.executable, str(APP/'mobile/check_serena_coverage.py'), '--base', str(voice)], ROOT))
    for command, directory in checks:
        result = subprocess.run(command, cwd=directory)
        if result.returncode:
            return result.returncode
    return 0

if __name__ == "__main__":
    sys.exit(main())
