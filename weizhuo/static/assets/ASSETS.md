# 视觉素材来源

本目录的标志、游戏图标、场景背景与筹码原图 由 **GPT Image（gpt-image）** 通过 Codex 内置图像生成工具生成。未使用外部图片库或第三方摄影素材。文字、数字、按钮、布局和动画由 HTML/CSS/JavaScript 实现，不是图片内嵌 UI。

生成素材随项目按根目录非商业与非赌博用途许可分发。第三方二维码依赖仍遵循自己的许可证，见根目录 `THIRD_PARTY_NOTICES.md`。

展示素材转换为 WebP（质量 85），图标缩至 256 px，筹码缩至 512 px；透明通道保留。标志保留 256 px PNG，兼容安装包图标。此处理不改变 GPT Image 来源；静态素材可缓存，身份与房间接口禁止缓存。

## 当前素材

| 文件 | 用途 |
| --- | --- |
| `weizhuo-logo.png` | 透明底围桌标志 |
| `zhajinhua-icon.webp` | 三张牌游戏目录图标 |
| `holdem-icon.webp` | 德州扑克目录图标 |
| `mahjong-icon.webp` | 自由记分目录图标；代码沿用 mahjong 标识 |
| `party-background-pro.webp` | 大厅深色毡布场景 |
| `holdem-scene-v2.webp` | 德州竖屏一体场景 |
| `holdem-scene-landscape-v2.webp` | 德州横屏一体场景 |
| `zhajinhua-scene-v1.webp` | 炸金花竖屏红绒木桌场景 |
| `zhajinhua-scene-landscape-v1.webp` | 炸金花横屏场景 |
| `free-score-scene-v1.webp` | 自由积分竖屏蓝布桌游场景 |
| `free-score-scene-landscape-v1.webp` | 自由积分横屏场景 |
| `holdem-chip-stack-v1.webp` | 透明底筹码堆，供奖池和运动反馈使用 |

场景使用完整俯视桌子与环境，横屏按相同材料重新构图。空桌不包含真实手牌、玩家、按钮或文字，角落留给操作，中心留给实时奖池与流程。提示词设计记录见 `docs/TABLETOP_UI.md`；历史德州素材演进见 `docs/HOLDEM_TABLE_UI.md`。

`holdem-table-v1.webp`、`holdem-table-landscape-v1.webp`、`holdem-floor-v1.webp` 为早期设计素材；当前牌桌最终样式使用一体场景。不要按旧图恢复已淘汰的交互。

## 运行截图

`screenshots/` 下 JPG 来自应用实际运行，使用虚构玩家和测试房间，不属于生成图片。记录见 `screenshots/README.md`。主 README 的截图链接指向这些文件，截图更新必须与实际产品一致。


### 服务首页与宣传启动页（2026-10-05）

- `service-home-background-v2.webp`：GPT Image 生成及编辑；奶白、浅鼠尾草绿，边角为棋盘、木质棋子、骰子和卡牌，中央留给真实控件。
- `service-launch-poster-v2.webp`：GPT Image 生成及编辑；桌上为通用桌游，无麻将；围桌宣传启动画面，包含“线下游戏，线上记分”“仅需局域网 · 无需互联网”。
- 使用内置图片生成工具，导出压缩 WebP；iOS 原生运行素材由 `mobile/prepare.py` 派生 JPEG / PNG，不包含用户数据。生成提示和使用方式见 [服务页素材说明](../../../docs/SERVICE_ART.md)。

### iPhone 德州场景扩展（2026-10-05）

旧版 v3（已从分发资源移除）由内置 imagegen 参考 `holdem-scene-v2.webp` 编辑生成，按 iPhone 393:852 比例向上下补全木地板环境，不拉长桌体。曾用于 iPhone 竖屏，现使用 v4；文字与流程另按安全区布局。提示词：保留绿绒桌面、棕色皮革桌沿、木地板及暖光，将桌子上下的房间环境自然扩展，顶部留出灵动岛和流程栏空间；保持俯视、对称，无人物、筹码、界面、文字和水印。

`holdem-scene-iphone-v4.webp`：内置 imagegen 编辑 v3，保留顶部安全区与桌宽，把底部桌沿由画面约 76% 推至约 86%，自然重绘绒布与皮革纹理，收回下方多余环境。对应座位沿新桌沿重新计算，画布与纹理不直接拉伸。提示词：保留俯视、顶部桌沿位置、宽度及暖光，将下半段牌桌自然重绘到画面约 86%，底部保留约 13% 木地板用于角落按钮；无界面、文字、人物或筹码。
