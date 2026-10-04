# 启动器、CLI 与桌面构建

## 源码启动

`python3 weizhuo/server.py`（Windows 使用 `py -3 weizhuo\server.py`）启动局域网服务；没有独立安装的 `weizhuo start/stop/status` 命令。

`scripts/bootstrap.py` 离线检查 Python、SQLite、内置二维码和必要文件，不安装软件、不接触真实数据库、不启动服务。`--test` 另运行完整检查，需要 Node.js。

macOS 可双击 `scripts/start-scoreboard.command`，Windows 可双击 `scripts/start-scoreboard.cmd`，仍需 Python。关闭终端停止服务，数据库保留。

## 桌面应用

桌面应用名称为 **围桌**：macOS 为 `围桌.app`，Windows 为 `围桌.exe`。启动器 `weizhuo/desktop/launcher.py` 显示局域网地址，提供启动/进入大厅和关闭服务两个按钮。界面仍在浏览器中；应用启动后打开大厅。停止或关闭前确认，房间和积分保留。启动时由系统自动选择可用端口，大厅与邀请二维码使用实际端口；不会停止已运行的另一个服务。

打包应用自带 Python、Tk、规则引擎、二维码和静态素材，无需用户另装 Python。首次启动是独立数据目录，不会自动读取源码版的牌局。迁移前停止两边服务、备份并复制两份 SQLite 数据库，见 [备份说明](BACKUP.md)。

| 平台 | 当前验证情况 |
| --- | --- |
| macOS Apple Silicon / arm64 | 本机构建 `.app` 和 ZIP 成功；启动器界面打开，冻结包 HTTP、二维码、素材和重启自检通过。未验证其他 Mac。 |
| Windows | 已配置 GitHub Actions 构建 `.exe` 便携目录；尚未运行或在实体 Windows 验证。 |
| Android / iOS | 独立移动工程，见 [移动 App](MOBILE.md)；iPhone 有个人签名测试构建，公共分发仍需适用签名。Android 尚未完成构建验证。 |

macOS 包只使用临时签名，未使用 Developer ID 或完成公证；Windows 尚未签名。首版属于测试分发，不能声称已获得系统信任认证。Windows ZIP 必须完整解压，保留 `围桌.exe` 同目录的文件。macOS ZIP 解压后可将 `围桌.app` 放入应用目录。

Mac 本地构建使用 ad hoc 签名，不依赖 iPhone Personal Team 的 7 天描述文件期限。公开分发若要通过默认 Gatekeeper 检查，需要 Developer ID 签名与 Apple 公证；当前包尚未完成这两项。普通 Developer ID 应用未使用高级能力描述文件时，已签署的版本不会仅因签名证书或开发者会员到期而停止运行；证书撤销、系统兼容性和安全检查仍可能影响运行。见 [Apple 签名有效期说明](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/)。

主持期间保持主机唤醒；应用退出或主机休眠会中断连接。应用不自动改变防火墙、路由器或电源设置。

## 数据与升级

- macOS：`~/Library/Application Support/Weizhuo/`
- Windows：`%LOCALAPPDATA%\Weizhuo\`
- Linux 源码启动器：`$XDG_DATA_HOME/weizhuo/`，缺省为 `~/.local/share/weizhuo/`

正式库 `scoreboard.sqlite3` 与测试库 `test_scoreboard.sqlite3` 分开保存。替换应用不会覆盖用户数据；删除应用不会自动删除数据。备份或迁移请先停止服务，勿复制正在写入的库。服务首页自动检测稳定的 IP 变化，提示重启，由房主确认后重启并重新分享二维码。检测不会自动中断服务。浏览器身份与访问来源有关，换主机或地址前保存个人身份牌。

## 构建

在目标平台使用带 Tk 的 Python 3.11+（推荐 Python.org 发行版）。Mac 构建要求 Tk 8.6.13 或以上；构建脚本会检查版本，避免旧 Tk 窗口释放引发退出崩溃：

```sh
python -m venv .venv
# 激活环境后：
python -m pip install pyinstaller==6.16.0 pillow==11.3.0
python scripts/versioning.py --sync
python scripts/build-desktop.py --arch arm64
```

构建脚本收集应用资源、不收集运行数据库，运行冻结后的自检，再生成 ZIP 与 SHA-256。首次收集 Python / Tk / PyInstaller 许可证需联网。输出在 `dist/`，不提交 Git。应用名称使用中文；ZIP 文件名仍使用 `weizhuo-版本-平台-架构`，方便下载和自动化处理。用户数据目录保持原有 `Weizhuo` 名称，以兼容已有数据。源码运行不需要这些构建依赖。

`.github/workflows/desktop-release.yml` 可手动运行，也会在推送 `v*` 标签时运行；它只生成构建产物，**不自动创建或发布 Release**。每个产物注明平台与架构，公开前应补充目标机器上的多人局域网测试。

参考：[PyInstaller 使用说明](https://pyinstaller.org/en/stable/usage.html)、[运行时资源](https://pyinstaller.org/en/stable/runtime-information.html)。


## 桌面服务首页

桌面首页使用围桌图标与“线下游戏，线上记分”主题，填写本机局域网 IPv4 后启动。启动自动选择可用端口并打开浏览器大厅，主按钮变为“进入大厅”；回到服务首页或关闭浏览器不会停服。关闭服务及退出应用需确认，房间与积分保留。启动、关闭和打开浏览器期间显示进度，操作失败显示原因。

版本及五平台发布约定见 [发布说明](RELEASING.md#五个平台包与版本管理)。构建脚本验证实际 Python 架构，按版本、构建号、平台及架构隔离输出，避免互相覆盖。

按平台执行的完整命令、移动统一入口和签名边界见 [客户端构建教程](BUILD_CLIENTS.md)。
