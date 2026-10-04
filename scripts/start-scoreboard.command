#!/bin/zsh
cd "${0:A:h}/.."
if /usr/bin/curl -fsS http://127.0.0.1:8765/api/bootstrap >/dev/null 2>&1; then
  python3 -c 'import sys; sys.path.insert(0,"weizhuo"); import server; print("游戏大厅：http://" + server.lan_ip() + ":8765/")'
else
  if [[ -x /usr/bin/caffeinate ]]; then
    /usr/bin/caffeinate -i python3 weizhuo/server.py
  else
    python3 weizhuo/server.py
  fi
fi
read '?按回车关闭窗口…'
