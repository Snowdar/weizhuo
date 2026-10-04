"""Offline runtime check; no installation, database access or service startup."""
import argparse
import io
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description='围桌环境自检：无需下载运行依赖。')
    parser.add_argument('--test', action='store_true', help='自检后运行完整回归检查（另需 Node.js）')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        print('需要 Python 3.11 或以上。', file=sys.stderr)
        return 1
    sys.path.insert(0, str(ROOT / 'weizhuo' / 'vendor'))
    try:
        import qrcode
        from qrcode.image.pure import PyPNGImage
        output = io.BytesIO()
        qrcode.make('weizhuo-runtime-check', image_factory=PyPNGImage).save(output)
        if not output.getvalue().startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('二维码输出异常')
        import sqlite3
        with sqlite3.connect(':memory:') as db:
            db.execute('select 1').fetchone()
    except (ImportError, OSError, ValueError) as error:
        print(f'环境检查失败：{error}', file=sys.stderr)
        return 1
    missing = [name for name in ('server.py', 'static/index.html', 'static/tabletop.js')
               if not (ROOT / 'weizhuo' / name).is_file()]
    if missing:
        print('源码缺少必要文件：' + ', '.join(missing), file=sys.stderr)
        return 1
    print('通过：Python、SQLite、内置二维码依赖及应用入口。')
    print('运行不需要 pip install、Node.js 或前端 build。')
    print('在仓库根目录启动：python3 weizhuo/server.py（Windows：py -3 weizhuo\\server.py）')
    if args.test:
        if not shutil.which('node'):
            print('完整回归检查另需 Node.js。', file=sys.stderr)
            return 1
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / 'check.py')], cwd=ROOT).returncode
    return 0

if __name__ == '__main__':
    sys.exit(main())
