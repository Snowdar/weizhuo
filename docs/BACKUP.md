# 备份与恢复

正式库 `weizhuo/data/scoreboard.sqlite3` 包含积分与身份凭证，备份也属于敏感文件。Git 不保存运行数据，不能替代备份。

## 在线备份

不要只复制运行中的主数据库文件；使用 SQLite backup 接口获取一致快照。在项目根目录运行：

```sh
python3 - <<'PY'
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
source = Path('weizhuo/data/scoreboard.sqlite3').resolve()
target = Path('weizhuo/data/backups') / ('manual-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
target.parent.mkdir(parents=True, exist_ok=True)
with target.open('xb'):
    pass
target.chmod(0o600)
with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
    with closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
print(target)
PY
```

管理员备份在 `weizhuo/data/backups/`。

## 恢复步骤

1. 协调玩家，正常停止服务，确认没有其他进程访问数据库。
2. 保留现有主文件及同名 `-wal`、`-shm`、`-journal` 文件为独立副本。
3. 对备份执行 SQLite `PRAGMA integrity_check`，应得到 `ok`。
4. 将备份复制为 `weizhuo/data/scoreboard.sqlite3`，移走旧辅助文件，避免旧日志与恢复数据混用。
5. 启动后核对房间码、积分与对局。恢复回到备份时刻，之后操作不会重放。

测试库不得替换正式库；源码升级保留数据。新克隆不含旧房间，应另行恢复经过验证的备份。
