# 德州扑克游戏桌改造

> 本文包含设计演进记录，早期的独立背景、左下角操作面板及按钮颜色等已被后续设计替代。当前开发以根目录 `AGENTS.md` 和 `docs/TABLETOP_UI.md` 为准；不要把历史段落当作最终交互规范。

牌桌自适应剩余视野，主页面不滚动。每位玩家的本机视角都将自己旋转到最下方，保持现实座位的逆时针关系。玩家座位合并昵称、剩余积分、准备/弃牌/全下状态、庄位和本轮投入，点击座位查看下注明细及局间管理。自己的昵称单独标识，其他行动者高亮。

“沉浸牌桌”隐藏房间标题、房间号和顶部流程，桌面填满视野，设置随本机保存。左上角切换沉浸；右上角更多菜单查看房间、邀请、身份、奖池、结算、动态；底部两角分别为我的操作与发牌助手。横屏使用专门绘制的横向牌桌素材，非沉浸状态也压缩顶部信息。

轮到自己时自动打开操作面板；关闭后同一行动机会不会反复弹出，可从“轮到我·操作”再次打开。完成个人行动后收起。发牌助手独立打开，用于收盲注开局、确认发牌、代记线下动作、逐池派奖、撤回和撤销本局。助手面板在阶段变化后保持打开；轮询保留加注草稿与输入焦点。只有面板或弹窗内容较多时在内部滚动。

线下玩实体牌，桌面不虚构牌面。先在德州扑克验证，之后再迁移其他游戏。验证重点：2–10 人座位、手机短屏、横屏、全下跑牌、助手与玩家重合、边池多赢家、自动弹出及手动收起。

## 视口约束

进入牌桌时给根节点启用 `table-viewport`，固定 body，并禁止根节点与 body 滚动和回弹；离开房间时解除，恢复大厅的正常滚动。使用 `visualViewport` 计算实际可见宽高及偏移，没有该接口则退回 `innerWidth/innerHeight`；监听 resize、orientationchange 和可视视口变化，在下一帧重新适配。双指缩放不会缩小桌面布局。单指在桌面滑动被拦截，只有操作面板、详情弹窗与明确可滚动的信息区域保留滚动。

面板与原生弹窗按实际可视视口居中或贴底，键盘展开后高度也跟随缩小，超长内容在面板内部滚动。回归检查包含页面 scrollHeight/scrollWidth、实际视口尺寸、滚动后 scrollX/scrollY、横竖屏切换和视口尺寸计算。

## 画图素材

使用内置 imagegen（用户指定 gpt-image 画图）生成 `weizhuo/static/assets/holdem-table-v1.webp`。实际生成提示词：

Use case: stylized-concept. Asset type: production background asset for Weizhuo mobile portrait Texas Holdem scorekeeping game table. Draw ONLY an empty poker table viewed perfectly top-down, portrait canvas 1024x1536. One tall oval table centered, occupying 86 percent canvas width and 90 percent height, dark forest green finely textured felt, tasteful warm walnut padded rim with subtle golden stitching. Surrounding background pale warm sage matching a calm Chinese social scorekeeping app. Restrained polished tactile 3D illustration, soft ambient shadows, clear spacious center where live pot and phase labels will be overlaid by HTML. No players, seats, cards, chips, lettering, numbers, logos, watermark, controls or UI. Entire rim visible; symmetric top down, no perspective tilt. Keep visual noise low, elegant intimate friends around a table atmosphere.

横屏素材：`weizhuo/static/assets/holdem-table-landscape-v1.webp`，同样使用内置 imagegen，参考竖屏素材生成。提示词：

Use case: style-transfer. Production landscape poker table background asset. Create a horizontal wide landscape version of this exact Weizhuo table style: perfectly top-down broad horizontal oval poker table, forest green textured felt, warm walnut brown padded rim with golden stitching, pale sage surrounding surface, soft shadows and faint leaf shadows in empty outer corners. Horizontal canvas 1536x1024, table occupies 94% width and 88% height. Same materials and restrained lighting. Empty central felt for live HTML score overlay. No letters, numbers, cards, chips, seats, people or user interface.

筹码素材：`weizhuo/static/assets/holdem-chip-stack-v1.webp`，内置 imagegen 生成，保留透明通道。提示词：

Use case: stylized-concept. Production transparent UI sprite for Weizhuo warm calm poker scorekeeping app. One compact pile of three small poker chip stacks, one taller cream-and-gold stack, one muted forest-green-and-cream stack, one shorter warm rust-and-cream stack. Restrained tactile polished 3D illustration matching a dark green felt and walnut rim poker table. Viewed from near top-down with slight 3D depth. Centered tightly, no surrounding props, no lettering, numbers, denominations, cards, coins, currency, logos or watermark. Soft small contact shadows contained beneath stacks. Genuine transparent background. Clear silhouette legible at 60 pixels.

新增正数投入从对应座位飞向奖池，显示本次投入；退款、撤回、重复轮询、刷新和重进不重播。新一局收盲注可以播放。动画层独立于重新渲染的桌面，使用 transform/opacity，不改变布局；遵从系统减少动态效果设置。


## 座位操作与控制台（2026-10-04）

准备、下注及确认发牌直接显示在本人卡片上方，金色表示玩家操作，蓝色表示发牌协助。房主无需准备，其他玩家有积分且全部准备后，房主可开始。本人回合结束后操作自动消失。

卡片按人数沿桌沿自动排布，本人固定在最下方；为本人操作留出底部空间。左下角座位编辑只交换两人的顺序，支持拖动和依次点选，保存后同步到所有客户端。局间才能编辑，人数变化时丢弃过期草稿。

右下角控制台提供积分调整、撤销、代替行动、下一局庄位和发牌协助者指定。积分与庄位只在局间调整，庄位指定一次后恢复正常轮转。房间设置仅保留房间名、创建时的游戏参数及销毁。

底牌发牌时，先收牌玩家显示标记，中央提示逆时针两圈；多人先发给小盲，双人先发给大盲。后续公共牌提示先烧牌再发牌。奖池金额固定在桌面几何中心；窄屏、矮屏和横屏分别压缩操作，避免遮住卡片。信息弹窗只保留右上角关闭按钮，编辑弹窗保留保存操作。

玩家编号固定在昵称前；编号跟随玩家身份，不随换座、观看视角或重新进入而变化；新玩家领取递增编号，已离开玩家的编号不复用。长昵称只在名称区域自动往返滚动，编号固定；减少动态效果时改为手动横向滚动。

编号采用金色小矩形，固定在名字前。座位以可见桌沿的弧长均分，随实际视口尺寸重新计算，避免长椭圆上方拥挤。点击卡片直接进入本局下注账单，按阶段列出动作、时间、实际投入及退还；详情打开时持续同步，编辑表单仍暂停轮询以保留输入。

座位路径已进一步校准为与素材一致的胶囊形桌沿：按完整周长等距采样，本人位于底部中央，其他座位左右镜像。背景与座位共享内缩参数，边缘卡片保持在视口内。行动面板根据本人卡片位置及相邻卡片边界调整宽度。协助面板恢复标题在上、短按钮在下的布局。

### 2026-10-04：整屏背景与卡片旁记录

- 场景背景独立铺满牌桌主视图，四角按钮也覆盖在纹理背景上；牌桌照片竖屏左右留 16px、上下留 48px，横屏左右留 48px、上下留 16px，边缘以 12px 羽化过渡，消除照片外的纯色条带。
- 座位仍沿照片对应的对称胶囊形边缘，按周长等距分布；边界计算同时考虑卡片尺寸，保证卡片完整显示。本人固定在下方，玩家编号随玩家保留。
- 点击玩家卡片在旁边打开 176px 宽的本局下注记录，优先左右、空间不足时上下展开，限制在视口内；再次点击、点击空白处、右上角 × 或 Escape 收起。记录随房间同步更新，不使用模态遮罩。
- 卡片悬停只过渡边框和阴影，保持不透明底色，避免背景渐变切换造成透明闪动。
- 生成素材：`weizhuo/static/assets/holdem-floor-v1.webp`，由 GPT Image 从原牌桌图片移除桌子、补全同色纹理与树影生成。提示：Remove the entire poker table including wood rim, felt and its shadows, reconstruct the sage olive beige softly textured floor seamlessly across the entire image. Preserve floor color, photographic texture, ambient lighting, foliage shadows near upper left and lower right. Background only, no table, objects or text.
- 验证 10 人桌在 320×568、520×827、844×390 下无卡片重叠、出界或页面滚动。

### 卡片结算与同步派奖

摊牌阶段直接在牌桌点选获胜玩家卡片，不再使用复选框弹窗。主池、边池分别保留选择，平牌支持多人；只有一位有资格的玩家时自动选中。选中卡片以金色边框和“待确认赢家”区分实际已派奖状态，所有奖池都有赢家后才能点击“结算”。只有一个奖池时不显示切换箭头；多池使用透明背景金色箭头，与奖池名称居中对齐。

`selectWinner` 由房主或发牌协助者提交，后台验证摊牌阶段、奖池资格和房间版本；`winnerSelection` 随房间状态向普通玩家同步（现有每秒同步机制）。选择不会改变积分，也不会清除撤销历史。玩家看到选择进度，但不能修改或结算。结算成功后显示“派奖 +分数”，筹码从奖池飞至赢家卡片，卡片及积分数字有高亮反馈；按每局结果去重，刷新进入不重播，尊重减少动画偏好。

验证：106 项后台测试与 UI 检查通过；真实测试接口以普通玩家身份读取到房主选择；测试桌单赢家派奖 100 分、双赢家各派奖 50 分，总积分不变；页面捕获到 `award-flight` 筹码及 +100 标识。

### 桌沿视觉校正与弃牌状态

竖屏桌子照片下移 8px，上沿座位路径上移 8px，下沿保持原有边界；左右对应座位仍镜像分布，采用周长自动布局。弃牌或无当前奖池资格的玩家使用不透明灰色卡面，标示“已弃牌”或“无此池资格”，控制端不能将其选作对应奖池赢家。普通玩家也显示牌局阶段、等待助手发牌、发牌步骤及当前行动玩家；底牌阶段额外提示助手与先收牌玩家。测试桌实际展示等待翻牌和弃牌灰卡，普通玩家接口确认相同阶段及弃牌者无奖池资格；320×568 检查无卡片重叠、出界或页面滚动。

### 非房主自动准备

非房主玩家左下角可切换自动准备，状态保存在该房间的玩家身份上。开启时，局间立即准备；牌局进行中只记录偏好，结算成功后由后台自动准备，房主仍需主动开始下一局。积分为零不会自动准备。手动取消准备会同时关闭自动准备；局间设置变更仍要求重新确认准备。切换偏好不清除撤销记录，撤销游戏动作也保留最新偏好。109 项后台测试通过，双人演示桌验证玩家开启后房主的“开始”立即可用。

### 奖池筹码规模与手机操作区

奖池筹码按金额相对大盲的规模分为六档；超过 80 个大盲的奖池增加轻微金色闪光。金额增长只改变固定区域内的筹码密度，不扩大图片的占用范围，原有下注及派奖飞行动画继续保留；减少动画偏好关闭闪光。

行动玩家的操作区移到桌面中央空白区域，按附近座位实际边界限制宽度。面板使用 74% 不透明的浅色背景，手机按钮为 11px，输入保持 16px 避免移动浏览器自动放大。竖屏去掉长说明的视觉占位，保留输入的无障碍标签；小屏将筹码放到奖池金额旁，横屏把奖池与操作并排，同时为顶部进度预留座位空间。准备按钮与助手消息继续独立显示。

浏览器尺寸验证：393×852（iPhone 16 常见逻辑尺寸）、320×568 与 852×393 十人桌，在本人可过牌、下注、弃牌、全下的实际测试牌局中，操作区与角色卡片无重叠，页面无纵向滚动。这里只验证浏览器视口，没有使用实体手机。


中央行动区优先保证可读的字号、金额及触摸按钮，可以覆盖下层桌面内容和角色卡片。行动区显示当前奖池，覆盖时隐藏下层重复奖池；回合结束恢复桌面。十人短屏不再依靠缩小面板避开所有卡片。助手按钮单独突出，赢家选择阶段仍保留合法角色卡片可点。


### 桌沿与全屏坐标（2026-10-08）

- 三种牌桌的角色位置依据场景图中的桌沿坐标，统一换算到实际背景渲染尺寸；普通视图与沉浸视图共用换算，不再按内容区的独立百分比移动卡片。
- 上下座位中心落在对应桌沿，左右座位沿同一条桌沿路径排列。背景采用 cover 时先计算裁切偏移，不能直接使用屏幕百分比。
- 异形屏的安全区由外围工具独立处理，座位表面不再增加顶部 padding。炸金花和自由记分必要时同步缩小场景展示范围，保留上下工具区域，卡片仍与实际桌沿对应。
- 德州和炸金花的动作记录整体居中在上方桌布内，记录文字左对齐、时间列固定；避让角色、流程、奖池的浮动文字与筹码，空间不足减少显示条数。
- 本次完成浏览器视口与安全区样式验证，未将其作为实体 iPhone 键盘或安装验证。
