# 发布检查清单

本文面向项目维护者，用于源码公开与安装包发布前的检查。仓库链接、版本号和下载入口须与实际发布结果一致。

## 已具备

- `README.md`：玩法、实际界面截图、源码安装、环境自检、配置、数据与架构图。
- `LICENSE`、`THIRD_PARTY_NOTICES.md`、应用素材 `ASSETS.md`：本项目非商业与非赌博用途许可、依赖原许可和 GPT Image 来源。
- `CONTRIBUTING.md`、`AGENTS.md`：贡献流程和真实使用场景优先的产品设计约定。
- `SECURITY.md`：可信局域网边界、凭证与漏洞报告邮箱。
- `.github/ISSUE_TEMPLATE/`、`PULL_REQUEST_TEMPLATE.md` 与回归 CI。
- `.gitignore`、`.env.example`、`CHANGELOG.md`、架构 / 玩法 / 备份 / 打包计划。
- macOS 源码启动脚本、Windows 源码启动脚本、离线 `bootstrap.py`。

## 首次公开前

1. 确认 GitHub 用户或组织、仓库名 `weizhuo`、公开范围及非商用、非赌博用途许可，然后更新 README 的源码获取方式，添加真实克隆命令，并把 `weizhuo/static/index.html` 的 `weizhuo-project-url` 元信息填为真实 HTTPS 仓库地址：大厅页脚将显示“GitHub: 实际仓库地址”链接。大厅当前预设 `https://github.com/Snowdar/weizhuo`，这是预计地址，不代表仓库已发布；发布时核对实际账户、仓库名及地址。配置为空时隐藏链接，学习交流、权利保留和禁止商用声明始终显示。
2. 运行 `python3 scripts/check-source.py --staged` 检查暂存内容（提交前先完成暂存）；工具只报告文件名与问题类型，不打印疑似凭证。此检查覆盖常见标记，不能替代人工审查。检查首次提交和所有旧历史：不能包含数据库、身份凭证、私人二维码、管理员私人码、日志或本机路径。忽略规则不能抹除旧提交；核对截图只用虚构测试数据。
3. 在干净源码目录运行 `python3 scripts/bootstrap.py`，启动服务并核对静态页面、二维码及可写数据目录；完整运行 `python3 scripts/check.py`，确认托管 CI 通过。
4. 至少用第二台局域网设备走通加入、重进、记分及停止后恢复。手机浏览器与 Windows 启动尚需实机确认，支持矩阵不能把未验证状态写成已支持。
5. 开启 GitHub 私密漏洞报告，保留安全邮箱；检查 Issue / PR 模板不要求上传凭证和真实库。
6. 源码与各平台包按同一版本准备；更新 CHANGELOG，注明升级备份及数据兼容性。macOS 仅分发 Apple Silicon（arm64）包，已完成构建自检；Windows 需完成目标平台验证；Android 发布前复核目标设备与签名；iPhone 仅提供自行签名构建指南，不上传通用安装包。仅上传真实构建、验证过的产物。

## 建议后续补充

- macOS / Windows / Linux CI 与真实用户 smoke test；先记录实际覆盖，再扩大支持声明。
- 可复现的截图示例流程和发布产物校验和；安装包提供升级、卸载及用户数据位置说明。
- 随贡献者增加补充行为准则和维护范围；小项目不必为了文件齐全而堆叠无实际执行的治理文档。
- 已补桌面构建脚本和目标平台工作流，执行并验证后再公布支持范围；无需为当前免安装运行依赖的源码版添加空 requirements 或 npm build。

发布前核对旧提交中的许可证文本与当前限制是否一致。更换当前许可不会自动撤销已按旧许可授予的权利；不要声称历史 MIT 内容被追溯限制，历史调整应经过维护者评审。

不承诺公网部署、云开发、多实例或跨平台自动服务控制；这些是独立开发事项。运行数据另行备份，不随源码发布。


## 四个平台包与版本管理

源码构建覆盖四个目标：macOS arm64（M 系列）、Windows x86_64、Android、iPhone。Release 计划提供 macOS arm64 ZIP 和 Android arm64 APK；Windows 预编译包后续再考虑，先提供自行构建指南，iPhone 由使用者在自己的 Mac 上本地签名构建，不上传通用 IPA。Mac 不再构建或分发 Intel 安装包。

`version.json` 是唯一版本来源。`version` 使用 `主版本.次版本.修订号`；`build` 是全项目单调递增的整数，重新分发修复包也必须增加，不能重复使用。各平台发布同一个源码提交、版本号与构建号；iOS `CFBundleVersion`、Android `versionCode`、Mac Bundle 和 Windows 文件版本均对应此构建号。版本号改变时仍继续增加构建号，避免 Android 拒绝升级。编辑后运行：

```sh
python scripts/versioning.py --sync
python scripts/versioning.py
python scripts/check.py
```

桌面构建文件名为 `weizhuo-0.1.0-build2-macos-arm64.zip`、`weizhuo-0.1.0-build2-windows-x86_64.zip`。Android 发布使用相同前缀加 `android.apk`；iPhone 仅提供构建与签名指南，不将个人签名测试 IPA 作为公共安装包。发布标签为 `v0.1.0`，测试重打包通过 build 区分；正式标签和 Release 仍需人工发布。

桌面工作流分别在 `macos-15`（arm64）、Windows runner 构建。它只上传工作流产物，不发布 Release。每个包附 SHA-256、版本元数据与冻结包自检报告；发布人核对包内版本，不只看文件名，记录操作系统、CPU、退出流程及多设备局域网测试结果。四个目标有任意一个未构建、未验证或签名不满足安装方式时，不标注为已全部交付。

Android 公共包须使用持续保存的发布密钥签名，后续更新沿用同一密钥；密钥不入仓库。本项目的 iPhone 路线是使用者本地构建并以自己的开发团队签名，Release 链接构建教程；个人开发签名存在有效期和安装范围限制，不能承诺通用扫码安装。未来若改变分发方式，应另行确定签名渠道并更新说明。数据兼容、备份、最低系统版本与签名状态写进各版 Release notes。

## 0.1.1.a1 / build 48 首次预发布

- 维护者已授权随源码提供 `resources/voice/` 正式 FP16 VITS 与 Serena 库，并发布现有 build 48 的 Mac arm64 ZIP 和 Android arm64 APK。VITS 许可核查结论保留；不声称获得完整权重授权。
- 包在正式资源入库前已经构建；本次新增的是资源归档、准备脚本、检查和文档，App 运行代码没有改变。Release 附包原 SHA-256，包内版本及签名状态以 build-info 为准。
- Android 使用现有本地测试签名，Mac 未公证；这是测试预发布，不声称应用商城或正式渠道签名。后续升级须保留兼容签名。
- iPhone 个人签名 IPA 不上传，Windows 尚无已验证产物。
