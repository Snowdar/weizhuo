# 从源码构建围桌客户端

本文面向自行构建的开发者。运行记分网页不需要打包客户端：安装 Python 3.11+，在仓库根运行 `python3 scripts/bootstrap.py` 和 `python3 weizhuo/server.py` 即可。客户端负责在服务设备启动相同的 Python 服务，朋友扫码用浏览器加入。游戏运行无需互联网；首次准备构建工具和下载依赖通常需要联网。

源码无需 npm、前端编译或云服务。以下命令以包含 `README.md`、`version.json` 和 `weizhuo/` 的目录为仓库根。不要把个人数据库、开发证书或模型下载目录纳入 Git。

## 使用 Agent 帮助构建

将本仓库与目标平台提供给 Agent，例如：“按 BUILD_CLIENTS.md 在这台 Apple Silicon Mac 构建围桌，并核对版本与启动。”Agent 应先检查主机架构、Python 和平台工具，执行下面的环境准备与构建步骤，核对最终包内资源，使用独立测试数据验证。无需自己熟悉全部构建命令，但仍需亲自完成所需账号登录、SDK 许可确认和签名选择。

| 目标 | 构建主机 | 额外条件 |
| --- | --- | --- |
| macOS arm64 | Apple Silicon Mac | 带 Tk 的 Python、PyInstaller。 |
| Windows x86_64 | Windows 电脑或 runner | 带 Tcl/Tk 的 Python、PyInstaller；Mac 不能直接构建此包。 |
| Android | Mac、Windows 或 Linux | Briefcase、JDK、Android SDK；公开包需自己的发布签名，验证需安卓设备或模拟器。 |
| iPhone | Mac | 完整 Xcode、iOS SDK、自己的 Apple Team；真机需连接并开启开发者模式。 |

发布计划仅提供 Mac ARM64 ZIP 和 Android ARM64 APK；Windows 可使用 Agent 在 Windows 上自行构建，预编译包后续再考虑增加；iPhone 由使用者自行本地签名构建，不提供通用 IPA。未完成的平台不列为已交付，可用产物以 Release 实际文件为准。正式 TTS 资源在 `resources/voice/` 随仓库提供，第三方许可状态单独记录，见 [第三方说明](../THIRD_PARTY_NOTICES.md)。

## 构建前检查

```sh
python3 scripts/bootstrap.py
python3 scripts/versioning.py
# 完整回归另需 Node.js
python3 scripts/check.py
```

版本来自 `version.json`。修改版本后运行 `python3 scripts/versioning.py --sync`；所有同版包使用相同源码和 build。构建工具按平台生成不同文件，不能把一个平台的产物改名充当另一个平台。

## 四端语音资源

- 四端使用相同 `weizhuo/mobile/.voice-assets/Voice`，其中 VITS 使用 `model.onnx`（配置后可用 FP16 权重替换）、词典和数字规则；Serena 使用已采纳的 `Serena/manifest.json` 与引用 WAV。正式 FP16 权重及 Serena 音频已在 `resources/voice/` 随仓库提供，`.voice-assets/` 是本地构建副本。
- 准备 VITS 和对应原生运行库：`python weizhuo/mobile/provision_voice.py --platform desktop`、`--platform android` 或 `--platform ios`。首先校验并复制仓库内声音，仅平台运行库需要下载，现有 Voice 不会被覆盖；安卓 AAR 校验固定 SHA-256。
- Serena 素材按 [离线播报说明](OFFLINE_VOICE.md) 与采纳记录准备并运行 `check_serena_coverage.py`，不能把开发候选全部打包；发布说明须保留 VITS 上游许可未明确的现状。完整四音色构建须先运行资源准备命令，将仓库内正式资源复制到构建目录。
- Android 构建嵌入 AAR、模型及已采纳片段；桌面构建收集 sherpa-onnx 和 ONNX Runtime 动态库，缺少语音资源会报错，避免静默产出缺功能包。iPhone 保留原生框架配置。

## macOS：Apple Silicon（M 系列）

在目标架构上安装带 Tk 的 Python 3.11+。构建脚本要求 Tk 至少 8.6.13，Tk 较旧时先升级 Python/Tk。检查所用解释器架构：

```sh
python3 -c "import platform,tkinter; t=tkinter.Tcl(); print(platform.machine(),t.call('package','require','Tk'))"
python3 -m venv .venv-desktop
.venv-desktop/bin/python -m pip install pyinstaller==6.16.0 pillow==11.3.0 sherpa-onnx==1.13.8 numpy==2.3.3
.venv-desktop/bin/python scripts/versioning.py --sync
# Apple Silicon 原生解释器
.venv-desktop/bin/python scripts/build-desktop.py --arch arm64
```

Mac 分发目标仅为 arm64，不再提供 Intel 安装包。脚本核对 Python、冻结程序架构，运行 HTTP/资源/停止重启自检，并生成 `围桌.app`、ZIP、SHA-256、版本元数据和报告。产物在 `dist/<version>-build<build>/macos-arm64/`。

当前构建是本地 ad hoc 签名，没有 Developer ID 公证；具体安装与数据迁移见 [桌面说明](PACKAGING.md)。自检不代表已经在另一台 Mac 测试。

## Windows x86_64

在 Windows 安装 Python 3.11+（包含 Tcl/Tk），在 PowerShell 执行：

```powershell
py -3 -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install pyinstaller==6.16.0 pillow==11.3.0 sherpa-onnx==1.13.8 numpy==2.3.3
.\.venv-desktop\Scripts\python.exe scripts\versioning.py --sync
.\.venv-desktop\Scripts\python.exe scripts\build-desktop.py --arch x86_64
```

输出为 `dist/<version>-build<build>/windows-x86_64/` 下的便携 ZIP；必须完整解压，不能只复制 `围桌.exe`。Mac 不能直接交叉构建这个 Windows 包。仓库的 `desktop-release.yml` 已保存目标系统构建步骤，也可手动触发生成工作流产物；该工作流不会发布 Release。当前 Windows 工程尚未完成目标机器验证。

## 共用移动环境

推荐 Python 3.13；在仓库根执行：

```sh
python3 -m venv weizhuo/mobile/.venv
weizhuo/mobile/.venv/bin/python -m pip install -r weizhuo/mobile/requirements-build.txt
```

Windows 对应解释器为 `weizhuo\mobile\.venv\Scripts\python.exe`，可将下面命令中的解释器路径替换为它。固定的 Toga 平台版本位于 `weizhuo/mobile/pyproject.toml`。默认干净源码构建没有神经语音权重；iPhone 使用设备系统音色。可选本地音色的来源、获取、转换与质量检查见 [离线播报](OFFLINE_VOICE.md) 和 [第三方说明](../THIRD_PARTY_NOTICES.md)。

## iPhone / iOS 模拟器

需要 Mac、完整 Xcode 和目标 iOS SDK；只有 Command Line Tools 不够。可先查看命令计划，再首次创建并构建：

```sh
weizhuo/mobile/.venv/bin/python scripts/build-mobile.py iOS --create --plan
weizhuo/mobile/.venv/bin/python scripts/build-mobile.py iOS --create
# 修改源码后的常规更新：
weizhuo/mobile/.venv/bin/python scripts/build-mobile.py iOS
```

脚本依次同步版本、收集运行资源、创建或更新工程、应用项目配置及构建。`configure_android.py` 在每次更新后替换所有密度的桌面图标、自适应图标、启动图与 Android 12+ 系统启动主题，避免模板小蜜蜂残留。

`configure_ios.py` 会核对网页、服务代码与版本是否最新，再配置窗口生命周期、启动画面及可选音色。不应直接跳过 prepare/update 去重打旧工程。

生成的工程为 `weizhuo/mobile/build/weizhuomobile/ios/xcode/围桌.xcodeproj`。在 Xcode 打开它、选择 `围桌` Scheme 和模拟器，点击 Run。命令行也可在 `weizhuo/mobile/` 执行：

```sh
xcodebuild -project 'build/weizhuomobile/ios/xcode/围桌.xcodeproj' -scheme 围桌 \
  -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16' \
  -derivedDataPath build/simulator build
```

模拟器名字以 Xcode 中已安装的设备为准。真机需选择自己的 Signing Team、连接设备并开启开发者模式；详细步骤见 [iPhone 安装](MOBILE.md#iphone-构建与安装)。在 Xcode 选择设备运行，或 Archive 后按适用渠道导出。模拟器 `.app` 不能装到真实 iPhone；个人签名构建不是通用 IPA。签名账号、证书与分发渠道由构建者配置，项目不保存私人凭证。

## Android

首次创建：

```sh
weizhuo/mobile/.venv/bin/python scripts/build-mobile.py android --create --debug-apk
# 已有工程在源码修改后更新：
weizhuo/mobile/.venv/bin/python scripts/build-mobile.py android --debug-apk
```

Briefcase 管理 JDK、SDK 和 Gradle 工程；首次需开发者阅读并接受 Android SDK 许可。产物位置以 Briefcase 最终输出为准，可在 `weizhuo/mobile/dist/` 查找 APK。调试包可用 `adb install -r <实际APK路径>` 安装，或传入手机后从文件管理器打开。

公开分发需按 [Briefcase Android 打包说明](https://briefcase.beeware.org/en/stable/reference/platforms/android/gradle/) 使用发布签名；后续升级沿用同一密钥，密钥不入仓库。Android 手机包默认为 arm64-v8a，最低 Android API 24；x86_64 模拟器需单独构建。已有 Mate 60 实机启动、地址检测与声音测试，但新包仍需复核首次启动、键盘和局域网服务。调试签名或本地测试签名不等于公开发布签名。

## 构建后验收

核对最终包内的版本和关键网页资源，检查启动、首次输入、退出、再次启动及升级保留数据。手机要测试软件数字键盘、长昵称、多人座位和切换网络；模拟器通过不能替代真机。多人连接应使用独立测试房间，检查扫码加入、动作同步、声音、撤销与结算。安装包放在 `dist/` 等忽略目录，不随源码提交；公开发布步骤另见 [发布说明](RELEASING.md)。

## iOS 键盘原生回归

Apple Silicon Mac 上，启动独立测试模拟器后运行 `python scripts/test_ios_keyboard_tracker.py --simulator <模拟器 UUID>`。测试从当前原生桥接源码提取键盘追踪器，在 UIKit 中核对牌桌偏移锁定、解除后滚动和观察者切换；不复制另一套实现。此检查不能替代实体 iPhone 的软件键盘、首次聚焦、关闭键盘和局部记录滚动验收。

### 暖语素材复现

完整正式 Serena 库已包含在 `resources/voice/Serena/`，运行 provision_voice.py 即可准备，无需重新合成。以下是修改声音库时的开发流程：在开发机按 [离线语音](OFFLINE_VOICE.md) 的通用上下文流程生成、审核并导出，再放入 `weizhuo/mobile/.voice-assets/Voice/Serena/`。该目录仅保留 manifest 及被引用 WAV，原句、未选候选及审核报告不打入 App。校验 `serena_context_accepted.json` 的 manifest 哈希和覆盖后，按上述 prepare → update → configure → build 顺序打包。重新合成的音频哈希会变化，需要重新审查，不能套用本次采纳记录。缺少语音资源的源码构建不会凭空具有暖语素材。


### 0.1.1.a1：手机 Release 与模拟器分包

- 统一显示版本为 `0.1.1.a1`；平台数值版本为 `0.1.1`，内部安装编号为 39。后续包继续递增内部编号，不随 alpha 序号重置。
- Android 默认只包含 `arm64-v8a`，面向当前 ARM64 手机。x86_64 模拟器按需单独构建，不放入手机 APK；纯 32 位设备不在当前支持范围。
- 手机 Release 测试包：`weizhuo/mobile/.venv/bin/python scripts/build-mobile.py android --release-apk`。该命令沿用本机已有调试签名以覆盖此前测试安装，但构建类型为 Release；它不是公开分发签名。
- 模拟器独立包：`weizhuo/mobile/.venv/bin/python scripts/build-mobile.py android --emulator --debug-apk`。
- 本次保持四音色、FP16 模型和原始声音素材，不开启未经验证的 Java 混淆或音频有损压缩。
- iPhone 在已有签名配置下使用 `xcodebuild` 的 `-configuration Release`，数值版本不包含 alpha 后缀，服务页与大厅显示完整 alpha 版本。Windows 数值文件版本也保留内部编号，显示版本由共同元数据提供。
