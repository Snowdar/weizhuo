# 安卓 / iPhone 局域网 App

当前为开发工程。iPhone 已有个人签名测试安装并进行初步真机验证；Android 尚未完成构建和实机验证。暂无公开 APK / IPA 发布包。工程位于 `weizhuo/mobile/`，使用 Briefcase + Toga 包装原有 Python 服务、SQLite 与网页。安卓输出 Gradle 工程，iOS 输出 Xcode 工程，业务逻辑保持共用。支持同 Wi-Fi 的离线局域网；新增本机热点地址识别入口，系统热点兼容性仍需真机验证。当前不自动创建热点，不提供云服务或后台常驻保证。

iPhone 启动过渡页显示围桌主题宣传画面，服务首页采用与大厅一致的奶白卡片、圆角按钮与桌游主题背景，二者不占用原生标题栏；系统安全区域保留。

## 使用流程

1. 房主与朋友连接同一 Wi-Fi；也可由服务设备先在系统设置开启热点 Wi-Fi，朋友连接该热点。访客隔离网络可能无法互通。
2. 房主打开 App，选择“同一 Wi-Fi”或“本机热点”，自动识别地址（也可手动填写手机局域网 IPv4），点“启动服务”。
3. 服务自动选择本设备的可用端口，房主直接进入 App 内嵌的本机大厅，无需扫码；朋友邀请链接携带实际端口。房主在内嵌大厅创建房间，朋友用浏览器扫描大厅或房间二维码加入，无需安装 App。
4. 主持期间保持 App 在前台；启动时尝试保持屏幕常亮。切后台、手动锁屏、系统终止 App 都可能中断服务。尤其 iOS 不保证后台服务。
5. 大厅内的悬浮首页图标可展开“返回服务首页”；返回不关闭服务，再点“进入大厅”继续。首页自动检测网络地址，也可点“关闭服务”，关闭需确认。房间与积分保存在 App 私有数据目录；重新启动可继续。网络地址稳定变化后提示“重启服务”，确认重启后重新分享二维码；不会自动中断牌局。

App 首次安装拥有自己的数据库，并不会自动获取电脑上的旧房间。卸载 App 会删除其私有数据，备份和电脑迁入入口待补。已有网页个人身份在不同地址间可能需要重新扫描个人身份码；手机搬家后旧电脑的身份恢复链接也不能自动指向新服务器。

## 无互联网与热点

记分、身份恢复、二维码生成及房间数据均由服务机本地处理。运行时无需互联网，只有服务机需要安装 App；玩家连接现场网络后用浏览器加入。安装、下载依赖与签名准备和离线游戏运行是不同阶段。

- **无互联网的 Wi-Fi / 便携路由器**：所有设备连接同一个网络即可；路由器无需接入宽带，但应关闭访客隔离。安卓和 iPhone 均可使用。
- **系统热点兼容入口**：房主先在系统设置开启热点，App 选择“本机热点”后自动识别地址，朋友连接该热点并扫码。App 识别实际热点接口，不写死网关或端口；没找到地址时提示检查网络，不继续使用旧 Wi-Fi 地址。此路径尚未做热点真机互通验证，系统共享网络与设备隔离可能影响访问。
- **安卓无互联网本地热点**：Android 8 起提供 LocalOnlyHotspot API，可创建不共享互联网的 Wi-Fi 网络，适合无信号环境。当前 App 尚未接入该原生创建接口；后续需实现版本对应的运行时权限、热点凭据展示和 reservation 生命周期，并验证多人浏览器接入。普通系统热点能否在无 SIM / 无信号时开启依厂商而异。
- **iPhone 个人热点**：没有供 App 创建个人热点的公开 API，需用户在系统中开启；个人热点是蜂窝网络共享功能，是否可用受系统、蜂窝服务与运营商影响，不能承诺无信号时由 iPhone 单独提供热点。山区优先使用安卓本地热点或独立路由器，iPhone 可作为玩家加入。

连接 Wi-Fi 时出现“无互联网”不等于局域网不可用，玩家应保留连接，不切回其他网络。网页依据对服务机的实际请求结果判断连接状态，不因为浏览器的互联网在线标志为 false 停止同步；积分提交仍有超时且不会自动补发。切换网络后服务首页自动检测地址，提示重启服务。房主确认后重启，并重新分享二维码；房间数据保留，端口重新自适应分配。App 不会自动关闭用户开启的系统热点。

依据：[Android 本地热点](https://developer.android.com/develop/connectivity/wifi/localonlyhotspot)、[Apple 热点 API 限制](https://developer.apple.com/forums/thread/702058)、[iPhone 个人热点](https://support.apple.com/en-ie/111785)。

## 准备环境

推荐 Python 3.13。在仓库根运行：

```sh
python3 -m venv weizhuo/mobile/.venv
weizhuo/mobile/.venv/bin/python -m pip install -r weizhuo/mobile/requirements-build.txt
python3 scripts/versioning.py --sync
weizhuo/mobile/.venv/bin/python weizhuo/mobile/prepare.py
cd weizhuo/mobile
```

Windows 将虚拟环境路径改成 `.venv\Scripts\briefcase.exe`。准备脚本只收集服务、规则、网页和素材，不打包数据库、测试房间、凭证、截图或缓存。源码更新后重新运行准备脚本，已生成的平台工程还需要 `briefcase update <平台>`。版本号与构建号来自仓库根 `version.json`；更新后重新运行对应 `configure_ios.py` 或 `configure_android.py`，核对实际包内版本。发布约定见 [版本管理](RELEASING.md#五个平台包与版本管理)。

已有 iOS 工程每次更新必须按顺序执行，不能仅更新原生外壳：

```sh
# 在 weizhuo/mobile 目录
.venv/bin/python ../../scripts/versioning.py --sync
.venv/bin/python prepare.py
.venv/bin/briefcase update iOS
.venv/bin/python configure_ios.py
.venv/bin/briefcase build iOS
```

`configure_ios.py` 会核对暂存资源和 Xcode 工程内的网页、服务代码及版本，发现与仓库源码不一致时拒绝继续配置；重新收集并更新工程后再构建。

## 安卓构建与安装

```sh
.venv/bin/briefcase create android
.venv/bin/python configure_android.py
.venv/bin/briefcase build android
.venv/bin/briefcase run android
.venv/bin/briefcase package android -p debug-apk
```

Briefcase 可下载独立的 JDK 17 和 Android SDK。首次运行需要联网，并由开发者阅读、接受 Google SDK 许可。不能将未接受许可的环境称为构建完成。调试 APK 仅用于测试；公开分发使用 release APK，按官方说明签名，签名密钥自行安全保管，不提交仓库。安装时从文件管理器打开 APK，或使用 `adb install`；同一签名才能平滑升级保留数据。

首版申请 Internet、网络/Wi-Fi 状态权限；HTTP 用于可信局域网与本机 WebView，不连接云端。新增安卓系统版本的局域网运行时权限需按实际 target SDK 和真机检查。

## iPhone 构建与安装

需要 macOS、完整 Xcode 和目标 iOS SDK；仅 Command Line Tools 不够。

```sh
.venv/bin/briefcase create iOS
.venv/bin/python configure_ios.py
.venv/bin/briefcase build iOS
.venv/bin/briefcase run iOS
```

首次真机安装：

1. 在 Xcode 的 Settings → Accounts 登录自己的 Apple 账号。
2. 打开 `build/weizhuomobile/ios/xcode/围桌.xcodeproj`，选择围桌 Target 的 Signing & Capabilities，启用自动签名并选择自己的 Team。Bundle ID 须在该团队下可用。
3. 用数据线连接并解锁 iPhone，按手机提示信任电脑；在“设置 → 隐私与安全性 → 开发者模式”中开启，按提示重启后确认。
4. 在 Xcode 顶部选择实际 iPhone，点击 Run。若 Mac 钥匙串要求 codesign 访问开发密钥，由设备所有者输入 Mac 密码并允许；内嵌 Python 模块也需要签名。
5. 若手机提示开发者不受信任，按系统提示在“设置 → 通用 → VPN 与设备管理”中信任自己的开发者，然后重新运行。

免费签名用于个人测试，有有效期限制；TestFlight / App Store 发布需相应开发者资格、签名与审核。未签名构建只用于编译检查，不能直接安装；不要把模拟器构建称为可直接安装到 iPhone 的 IPA。

`configure_ios.py` 配置共享运行 Scheme，关闭与嵌入式 Python SQLite 冲突的 Thread Performance Checker，保留 Main Thread Checker。若自行重建 Scheme，可在 Edit Scheme → Run → Diagnostics 取消 Thread Performance Checker；Xcode 注入的检查器可能触发 `isBulkReadStatement` 断言，不能通过删除房间数据库处理。[相关上游修复](https://github.com/flet-dev/flet/releases/tag/v1.0.2)。

配置包含局域网用途说明和本地 HTTP 例外，不使用音频、定位等后台模式维持服务器。打包工具负责内嵌 Python 和 iOS 二进制模块；iPhone 个人签名安装与首次启动已做初步真机验证；多人完整流程、二维码互通、后台恢复及升级仍需持续实测。

## 支持范围与限制

iPhone 已初步验证个人签名安装、应用启动、Wi-Fi IPv4 识别、自动端口、本机 WebView 大厅及同 Wi-Fi HTTP 接入。安卓尚未完成真机验证，当前没有公开发布包。二维码互通、多人完整玩法、安装升级及不同机型布局仍需继续验证。

电脑数据迁入、备份入口、后台恢复仍待完善。房主需保持 App 前台，不支持锁屏主持。

参考：[Briefcase 安卓](https://briefcase.beeware.org/en/stable/reference/platforms/android/gradle/)、[Briefcase iOS](https://briefcase.beeware.org/en/stable/reference/platforms/iOS/xcode/)、[Python iOS 嵌入](https://docs.python.org/3.13/using/ios.html)。

可选原生界面自检：在移动虚拟环境安装 `toga-dummy==0.5.3 pytest pillow` 后运行 `.venv/bin/python check_ui.py`（需要先 prepare）。该检查不渲染真机界面。

## 实装前需要确认的边界

iOS 构建需要完整 Xcode、目标 iOS SDK 及签名配置。普通局域网 HTTP 文件下载不能替代 iPhone 的签名与安装流程。

- 首次个人测试优先用数据线连接 Mac，在 Xcode 设置 Signing Team 并安装至 iPhone；按 Xcode/设备提示完成开发者模式和信任步骤。已登记设备的分发或 TestFlight 需具备相应账号及签名条件。
- 扫码只能打开邀请或安装入口；下载 IPA 不等于可以安装。无线分发仍需有效签名、适当描述文件及对应分发通道；自托管安装涉及 Apple 要求的 HTTPS 资源。
- 房主启动即进入 App 内大厅；本机 WebView 使用回环地址，朋友使用 Wi-Fi IPv4 与实际监听端口。端口由系统分配，二维码以实际端口为准。不同设备 IP 不同，相同端口并不冲突。
- 普通邀请链接中的 IP 不能反推出 Wi-Fi 名称。待补充房主手动填写的网络名称提示；读取 iOS SSID 需满足 Apple 的 entitlement 和授权条件，不能把定位授权悄悄作为扫码前置条件，也不承诺普通网页能自动读取 Wi-Fi 名。
- iOS 后台可能挂起服务线程。局域网不提供持久消息队列保证，客户端的超时请求可能未到达或已经执行但响应丢失；目前积分动作不自动重发。离线排队需另行设计身份、顺序、过期、幂等和冲突处理，不能简单把请求稍后全部补发。

依据：[登记设备分发](https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices)、[后台执行模式](https://developer.apple.com/documentation/Xcode/configuring-background-execution-modes)、[Wi-Fi 信息权限](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.networking.wifi-info)、[导出安装分发](https://help.apple.com/xcode/mac/current/en.lproj/dev23ea8b877.html)。


### 房主声音

进入房间后，房主可在右上角桌面详情菜单切换“房主播报”“仅提示音”或“关闭”。其他玩家默认不出声。配置完整本地音色资源的 iPhone 和 Android 构建提供“清晰 · 系统”“松朗 · 男声”“悦然 · 女声”和“暖语 · Serena”四种播报，在同一菜单切换并由本机保存（Android build 36 起保存选择）；语速固定 1.0 倍。未配置资源的构建使用系统中文语音，记分不需要联网；先在界面点按一次，以允许短提示音播放。仅播报新成交及流程变化，刷新和重进不会播放旧账单。收取的待确认提醒只涉及本人的请求，不改变请求可见范围。主持时保持 App 在前台；后台不积压播报。网页只有找到本机中文音色时才朗读，否则保留短提示音。

### iOS 窗口兼容

`configure_ios.py` 会应用单窗口场景配置、启动素材与调试 Scheme。项目中的 `ios_scene.py` 将场景生命周期转交给 Toga 窗口，服务首页保留系统安全区；大厅和牌桌的网页容器铺到屏幕边缘，没有原生导航标题栏。牌桌场景覆盖灵动岛两侧及底部区域，文字、玩家卡片与操作按钮在安全区内排布，旋转后重新计算。使用 iOS 27 SDK 构建时不能省略该配置，参见 [Apple 的场景生命周期迁移说明](https://developer.apple.com/documentation/uikit/transitioning-to-the-uikit-scene-based-life-cycle)。

App WebView 禁用原生回弹与自动内容 inset，大厅保留正常滚动，牌桌按可视视口锁定。键盘打开时积分操作面板停在实际可见区域底部，方向切换重新计算。房主播报支持新发生的看牌、弃牌、过牌、闷注、跟注与加注金额，神经音色在后台线程离线合成，切换声音、静音或离开前台会取消旧播报；普通网页仍使用本机中文语音，不自动联网下载音色。开发构建资源及实测边界见 [离线播报](OFFLINE_VOICE.md)。

统一移动构建入口是 `scripts/build-mobile.py`，提供只显示执行顺序的 `--plan`、首次创建的 `--create` 和 Android 测试打包的 `--debug-apk`；各平台完整操作见 [客户端构建教程](BUILD_CLIENTS.md)。
