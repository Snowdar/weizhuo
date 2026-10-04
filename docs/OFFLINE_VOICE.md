# iPhone 离线播报

配置完整本地资源的 iPhone 构建提供四种播报：清晰（系统）、松朗（VITS 男声 sid=1）、悦然（VITS 女声 sid=2）、暖语（Serena 预制片段）。语速固定 1.0，选择保存在 App 设备设置中。房主在牌桌右上角菜单选择声音；Android 也使用相同 VITS 模型和 Serena 片段，由 sherpa-onnx 1.13.8 AAR 生成、AudioTrack 顺序播放；系统声使用 Android TextToSpeech。Mac／Windows 的房主在服务设备浏览器中选择同样四种音色：离线声由本机 Python sherpa-onnx 生成 WAV、Serena 保留原采样拼接，再由浏览器逐条播放。系统声由各平台提供，三种离线音色素材一致。Windows 代码与构建入口已接入，仍须目标系统验收。

更新安装保留设备音色选择；不支持的选项回退默认音色，不影响服务首页启动。iOS 从原生设置使用整数访问器读取编号，已有安装数据与首次安装分别验证。

只播报新动作；进入、刷新与重进不补播旧账单。离开前台、关闭语音或切换音色会取消旧任务。合成使用四线程 CPU，独立队列不阻塞记分服务；网页等待队列最多 128 条、超过 120 秒过期，原生每次只取一条并等待播放完成。连续动作保持顺序，不因下一句到达打断上一句。开局、发牌完成、行动和结算分别播报；自由积分请求发送与成交分开播报，不能把请求说成已经到账。提示铃随这一条播报一起排队，铃后约 300ms 开始语音，不能覆盖上一条。

## 本地开发构建

先运行 `python provision_voice.py` 获取固定校验值的模型及框架，再执行 `configure_ios.py`，随后正常构建 Xcode 工程。正式 FP16 VITS 和 Serena 已随 `resources/voice/` 入库，准备脚本校验并复制到 `weizhuo/mobile/.voice-assets/`；没有资源时使用系统语音。克隆仓库会获取约 192 MiB 正式语音资源，首次构建另需下载对应平台运行库，App 使用时不联网获取声音。来源和校验值在 `ios/voice/assets.json`。公共分发仍需确认模型与训练数据许可，见第三方声明。

## VITS 端侧生成延迟与测量边界

- **设备与引擎**：iPhone 16 实机，sherpa-onnx / ONNX Runtime，VITS zh-ll，四线程 CPU，语速 1.0。
- **生成方式**：每次在端侧生成完整句子的音频后再播放，不使用预合成音频缓存；下表为模型预热后的历史测试结果，不是本次重新测量。
- **合成耗时**：整句生成音频所需时间；模型预热后的合成不包含首次模型加载。
- **软件首声延迟**：独立测试 App 从点击到首个非静音音频回调的时间；不是麦克风测到的扬声器出声时间，也不是网页游戏动作到实际播报的端到端延迟。

| VITS 权重方案 | 预热整句合成中位数 | 软件首声延迟中位数 | 软件首声 P95 | 测试记录与限制 |
| --- | --- | --- | --- | --- |
| 原版 FP32 | 约 479 ms | 约 632 ms | 约 884 ms | 计划 40 次，保存 39 次；最后一次未写入原因未确认，不能据此认定崩溃。 |
| FP16 权重存储，计算保留 FP32 | 约 508 ms | 约 612 ms | 未报告 | 20 条测试中一次被后台挂起打断；剔除该条后的 15 条预热记录用于中位数统计。 |

- 两组条件未严格控制，FP16 数值与原版接近，不能据此声称加速或 P95 改善；FP16 是权重存储优化，不是全图 FP16 计算。
- 集成到围桌后，原生桥接每 300 ms 检查新事件，另有提示铃后约 300 ms 的等待；队列中已有播报还会增加等待时间。不能直接把上表视为集成后的动作到出声延迟，也不把不同环节的中位数机械相加当作实测结果。
- 冷启动、不同句长和金额、男女音色分别统计、整合后的端到端延迟、持续播报耗电与内存尚未完成量化；独立测试不代表这些指标通过。
- 当前女声为固定音色，不能靠调参数克隆 Serena；更换音色需完整句子试听。

## FP16 权重存储

原始模型的 473 个浮点权重均为 FP32。`convert_voice_fp16.py` 将权重存为 FP16，计算图与输入输出保留 FP32，通过 Cast 恢复为现有 CPU 算子需要的类型。模型从 115.49 MiB 减至 58.27 MiB，不涉及 INT8。运行时可能把 Cast 折叠为 FP32 权重，因此不声称全 FP16 运算、内存减半或速度提升。直接全图 FP16 转换在类型检查中失败，未采用。

开发电脑安装 `onnx numpy` 后执行：

```sh
python convert_voice_fp16.py .voice-assets/Voice/model.onnx .voice-assets/Voice/model-fp16.onnx
python configure_ios.py
```

配置时仅嵌入转换模型，仍命名为 `Voice/model.onnx`，不把原版与转换版一起塞入安装包。基础 CPU 校验中男女音色输出均为有限数，固定随机噪声为零的短 token 测试与原模型同长度，波形 RMSE 分别约 0.000174 和 0.000318；这只是数值校验，不能替代完整句子试听与实机性能测试。

FP16 权重存储版本另做了一组 iPhone 16 四线程测试：20 条中一次被后台挂起打断，剔除该条后的 15 条预热记录合成中位数约 508 ms、软件首声中位数约 612 ms，与原版接近。由于测试被打断且条件未严格控制，不据此声称加速或 P95 改善。独立测试 App 显示点击到播放调度及点击到非静音首声，并在切入后台时取消当前测量。

## Serena 预制播报

手机只播放开发阶段生成的 PCM WAV，不运行 Qwen 模型。音色来自 Qwen3-TTS CustomVoice 的 Serena，Qwen 大模型不进入仓库，已采纳的最终 WAV 随 `resources/voice/Serena/` 提供。开发环境使用 `requirements-serena.txt`；模型快照、指令、种子和裁剪来源应与试听报告一起保存。

历史版本采用独立短词库，存在拖音、音色变化及句中语调不连贯问题。新的候选与接入流程统一使用下述整句模板，不再提供孤立短词生成入口。上一版项目采用 50 条经试听或按 dots 审查标准选中的完整句子配方，淘汰旧的独立短词库；已安装的旧客户端需重新构建安装才生效。

## 当前 Serena 通用拼接库

初版 build 29 使用 `context-v2`：475 个上下文条目，保留 50 条已采纳的完整句子配方，479 个引用 WAV（约 32.4 MiB）。自由积分给出、收取与管理积分，炸金花与德州行动，开局、发牌、提醒及多人结算共用编号播报；金额按中文数值组合，不读昵称。不是只匹配有限试听句子。

优先播放完整配方，其余句子用动态规划寻找完整可覆盖路径，以减少缓冲接缝；常见金额连同“分”整体保留，更多整数使用百、千、万等上下文数位组。重叠前缀会回溯，不在失败后换成系统音色。对未来新增的未知动作仍明确保留文字与提示音，并要求扩展素材和回归。

采纳前通过 4,238 个编号／金额／事件组合的文件覆盖检查，包含从实际事件生成器提取的 385 种文案；30 条实际运行路径拼出的压力音频通过 dots 独立盲转写和质量审查。覆盖检查不是所有组合的人耳验收，模型审查也不代表逐句人耳试听。来源、切点派生与哈希记录于 `weizhuo/mobile/serena_context_accepted.json`；50 条历史完整配方来源仍见 `serena_accepted.json`。

## 整句模板与音频评审（开发候选流程）

`weizhuo/mobile/serena_templates.py` 使用完整句子合成后对齐取片段，替代将孤立短词分别录制的候选生成方式。生成工具只输出开发试听目录，由采纳工具将明确选中的候选写入应用素材。计划文件是 `serena_template_plan.json`，当前含自由积分、炸金花、德州及行动/结算的 8 类压力样例；这是算法验证集，不表示已覆盖所有运行时句子或任意金额。

1. 用相同 Serena 音色、语速、提示词生成完整句子的多个候选。金额与“分”同句录制，“现在请几号玩家行动”完整保留。原始录音、随机种子、提示词及缓存指纹全部保留，调整指令会生成新缓存。
2. 使用本地 Whisper tiny 的注意力对齐估计字词时间，按计划提取“玩家＋动作＋另一位玩家”与“完整金额＋分”等上下文片段。对齐 token 跨越所需切点时拒绝猜测切割，改用更长片段或重录。这个小模型的估计不等于精确音素标注。
3. 同句切片采用连续、不重叠的区间，并检查拼回原句是否逐样本相同。只清理整句外部近零静音；不单独剪数字首字，不删除词内停顿，不跨淡化覆盖辅音，不变调/变速。不同句的片段直接拼接，接缝新增间隔为零，继承原句已有停顿；接缝跳变被标记待检，不能以添加统一大间隔掩盖。
4. 导出多个组合、同文原始整句参考及接缝时间。时长检查排除明显拖音，信号检查提示突变；可选盲转写核对文字与金额。Whisper tiny 的识别误差与重复幻觉较明显，仅用于提示风险，不能以识别通过宣布播报自然，也不能把错误转写直接当成真实漏字。
5. 音频模型先盲转写，再听候选与同文整句参考，评估首字/数字漏读、拖尾、音色跳变、接缝、清晰度与饱满度。返回带时间的缺陷及分项评分；缺字段、未知结果、漏字或明确接缝问题均不能进入候选。模型通过仅为初筛名单，仍需人耳试听确认后才更新 App 素材。

示例（路径参数指向本机已有模型，不会自动下载）：

```sh
python weizhuo/mobile/serena_templates.py \
  --model /path/to/qwen-mlx-model \
  --aligner /path/to/whisper-tiny-mlx-4bit \
  --processor /path/to/whisper-processor \
  --output /path/to/audition --takes 2 --variants 4 --transcribe
```

`--prompt clear` 可比较另一套提示词；`--reuse-sources` 复用已合成完整句子，仅重做对齐和拼接。不将备选素材按音色“自动合格”，不复制未验收文件到 `.voice-assets`。

### 可选 Gemini / dots 评审

`review_serena.py` 是开发工具，使用明确配置的接口，不进入手机包。Gemini 支持原生音频输入；dots 中应选择支持音频的 dots3-note 模型，不能把 dots.ocr 或视觉模型当作音频评委。dots3-note 官方部署建议为多 GPU 服务，本项目不下载该模型到 Mac 或手机。[Gemini 音频说明](https://ai.google.dev/gemini-api/docs/generate-content/audio)、[dots3-note 音频与部署示例](https://github.com/studio-dots-ai/dots3-note-prev/blob/main/README_CN.md)。

```sh
# 在本机环境配置 GEMINI_API_KEY；不要把密钥写进仓库或聊天。
python weizhuo/mobile/review_serena.py --directory /path/to/audition \
  --provider gemini --model YOUR_AUDIO_CAPABLE_MODEL

# dots 服务须支持 audio_url 的 data:audio/wav;base64 输入。
# 私有服务密钥使用 DOTS_API_KEY，接口参数不包含密码。
python weizhuo/mobile/review_serena.py --directory /path/to/audition \
  --provider dots --model dots3-note-prev --endpoint https://YOUR_HOST/v1
```

该操作会把开发生成的 WAV 和预期文本发送至所选服务，可能产生服务费用。评审输出为 `audio-review.json`，记录供应商、模型及音频哈希，便于确认评价针对哪个版本；不存密钥。不配置接口时仍可本地生成和检查，但不能标记为已完成大模型听觉评审。2026-10-07 已通过官方 dots 接口实际评审，结果与采纳范围见下方音频评审记录。

### 采纳与接入

`adopt_serena.py` 将明确选中的整句候选导出为 `context-v1` 配方库。选择清单每项包括 `id`、`sha256`、`accepted: true` 与 `reviewNote`，指向实际听过/评审过的候选；音频哈希不一致、明确接缝缺陷及缺少复核记录会拒绝采纳。

```sh
python weizhuo/mobile/adopt_serena.py --audition /path/to/audition \
  --selection /path/to/accepted.json --check-only
python weizhuo/mobile/adopt_serena.py --audition /path/to/audition \
  --selection /path/to/accepted.json
```

工具只复制被完整句子配方引用的片段，并核对这些片段拼出的 PCM 与被采纳整句逐样本一致。切换时先验证暂存库，保留一份 `.previous` 旧库以便恢复。应用将编号与金额归一为中文后匹配完整句子配方；缺少配方时保留文字和提示音，不切换系统音色，不重新退回短词拼接。原生播放使用 `preserveSamples`，不二次修剪片段边缘。构建过程排除 `.previous`、原始录音及评审报告，仓库仅包含正式 FP16 VITS 与已采纳 Serena 资源，不包含 Qwen 权重或 API 密钥。

完整流程计划为 `serena_flow_plan.json`，覆盖 44 种自由积分、炸金花和德州播报；其中有缺陷的候选重新录制或排除。历史完整配方的 50 条配方及 SHA256 记录于 `serena_accepted.json`。这一历史集合仅覆盖常用句子，不表示任意玩家编号、金额、多赢家或全场组合均已预录；匹配不到时保留文字和提示音，不切换系统音色、不混用旧短词。

完整模拟对局夹具保留在 `serena_scenarios.json`。整句生成工具可追加 `--scenario-file weizhuo/mobile/serena_scenarios.json`；这些数据用于按顺序生成自由积分、炸金花和德州的整句回归，不重新启用旧短词合成。

### dots 官方音频评审

官方平台接口见 [接口文档](https://dots.ai/platform/docs)。默认模型使用 `dots3-note-prev`，默认基础地址为 `https://note3-prev-api.askdiandian.com/v1`，认证头为 `api-key`；自托管兼容接口仍支持显式指定地址。只向服务发送用于评审的虚构编号播报，密钥在本机环境文件中保存，不进入手机或仓库。

```sh
python weizhuo/mobile/review_serena.py \
  --directory /path/to/auditions --provider dots --model dots3-note-prev \
  --env-file /path/to/local.env
```

环境文件只读取 `DOTS_API_KEY`，不执行文件内容。`--only` 可指定逗号分隔的候选编号；追加评审保留其他候选结果。先盲转写，再对照实际音频检查拖音、吞字和接缝，保存音频 SHA256 与评审提示。数字汉字与阿拉伯数字统一比较；同音异字仍保留供人工复核，不把字形差异直接描述成实际漏读。

完整提醒录音没有切点，跳过强制对齐，避免对齐模型拒绝本来完整的录音；转写和音频质量评审仍独立执行。整句候选通过后默认只进入试听初筛；本次已有试听采纳及明确按审查标准采纳的授权。每条采纳记录区分试听确认与模型标准采纳，不能将未逐句试听的候选宣称为人耳验收。

音频对照评审记录见 [Serena 音频评审](TTS_AUDIO_REVIEW.md)。

### 历史完整配方的复现与范围

生成完整流程候选时增加 `--plan weizhuo/mobile/serena_flow_plan.json`，再按上述 dots 命令评审；不要把首个候选默认视为合格。`serena_accepted.json` 保存本次选中录音的文字、来源组、哈希和采纳依据，不能直接用它给重新生成但哈希不同的文件背书。重新生成后须审查该批实际录音，按结果建立本批选择清单。

多批试听可以成对重复指定 `--audition` 与 `--selection`，一次合并采纳；工具先校验每批，再验证合并句子的采样和时长。重复完整句子须先选择一个版本，不能靠后写覆盖。

```sh
python weizhuo/mobile/adopt_serena.py \
  --audition /path/to/context-auditions --selection /path/to/context-accepted.json \
  --audition /path/to/flow-auditions --selection /path/to/flow-accepted.json
```

采纳后运行 `python scripts/check.py`。构建前按客户端构建文档重新准备和同步资源；不能只改声音目录就宣称已安装手机更新。构建导出的 Voice/Serena 仅包含清单引用的 WAV 和 manifest，不携带旧库、候选、评审报告或模型生成环境。未配置 Serena 素材的源码构建保留系统音色，其余离线神经音色仍按资源配置决定是否可用。

### 同音色的上下文变量拼接

暖语选择期间禁止系统音色补读。当前 50 条配方中 45 条保留整句，5 条由整句内的上下文片段拼出；还不是任意编号和金额的通用拼接库。缺少配方时不播放错误数字、不偷偷切换音色：界面保留完整记录，事件提示音照常播放，原生状态说明未覆盖。

`extend_serena_contexts.py` 从已审查的完整句子或已有上下文片段构建新的变量组合，不调用 Qwen 合成短词。`serena_context_extension_plan.json` 示例把整句中的完整“一千二百八十分”分别接到给分／跟注／闷注前缀后。每个新接缝重新提交 dots，不能以来源片段已通过审查代替组合的听觉审查；此次只采纳给分与跟注两个组合，闷注组合的同音转写仍待确认。

```sh
python weizhuo/mobile/extend_serena_contexts.py \
  --bank weizhuo/mobile/.voice-assets/Voice/Serena \
  --plan weizhuo/mobile/serena_context_extension_plan.json \
  --aligner /path/to/whisper-tiny-mlx-4bit --processor /path/to/whisper-processor \
  --output /path/to/context-extension
```

继续运行评审及采纳命令。提取只依据可对齐的字词边界，不估分切跨 token；连续切片须逐样本重建原句，不单独裁掉金额首字、不跨淡化、不添加统一大停顿。工具输出源码音频哈希与切点估计以供复核。完整录音优先，已有精确配方优先，不在运行时拼接任意未审查组合。

### 通用上下文库构建与验收

`serena_dynamic_plan.json` 列出通用变量模板：玩家编号、编号与动作前缀、完整常用金额和单位、较大数值所需的上下文数字，以及给出、收取、请求、结算和发牌流程。编号超过常用预录范围时以数字上下文组合，不播玩家昵称。Qwen 始终接收完整句子，不单独合成一个字。

生成工具的 `--quiet-boundaries` 在字词对齐位置附近寻找测得的低能量停顿；找不到可靠停顿时保留估计位置并交由组合试听检查，不以该步骤宣称获得精确音素边界。切片区间仍连续且逐样本还原原句。原句的相邻切片不构成新的波形接缝，不能把原波形正常的相邻采样差误判为拼接噪声；不同来源的新接缝需重新评审。

```sh
python weizhuo/mobile/serena_templates.py \
  --model /path/to/qwen-customvoice --aligner /path/to/whisper-tiny-mlx-4bit \
  --processor /path/to/whisper-processor \
  --plan weizhuo/mobile/serena_dynamic_plan.json \
  --output /path/to/context-candidates --takes 2 --variants 2 --quiet-boundaries
python weizhuo/mobile/review_serena.py \
  --directory /path/to/context-candidates --provider dots --model dots3-note-prev \
  --env-file /path/to/local.env --jobs 4
python weizhuo/mobile/build_serena_context_bank.py \
  --base /path/to/accepted-complete-sentences \
  --directory /path/to/reviewed-context-candidates \
  --cut-profile weizhuo/mobile/serena_cut_profile.json \
  --trim-context-silence --level-context --output /path/to/staged-bank
python weizhuo/mobile/check_serena_coverage.py \
  --base /path/to/staged-bank --output /path/to/assembled-auditions
python weizhuo/mobile/review_serena.py \
  --directory /path/to/assembled-auditions --provider dots --model dots3-note-prev \
  --env-file /path/to/local.env --jobs 4
```

导出工具只选取通过实际音频审查且哈希匹配的原句，校验切片 PCM，并删除未引用音频；导出目录还不是正式素材。已有完整句子优先播放，其他文本在完整覆盖条件下优先减少上下文接缝，常用金额与“分”整体播放，更多整数由同音色上下文数字组合。句内不人为增加统一空隙，完整录音跨逗号时沿用其录制停顿，其他明确分句边界使用短停顿。

覆盖检查包含实际手机试听文案、自由积分双方与多方交换、请求确认、各类扑克行动、流程、连续弃牌接结算、多人派奖和不同编号金额。覆盖通过只代表每个字词有对应文件，不能代替声学与听觉审查；组合音频仍有漏字、拖音、语调突变时，换素材或切点后重新审查。生产库更新、客户端重新构建、包内资源核对和实机试听是后续独立步骤。

`--allow-homophones` 仅供明确复核过的同音桌游用词（如“跟住／跟注”）比较，保留原始盲转写；不忽略金额变化、缺字或质量缺陷，不把“关注”当“闷注”。

实际发音字符才传入对齐模型，逗号等标点不占时间 token。原始连续分区先检查逐样本还原；离线派生阶段只裁外部确定静音并保留 35ms 保护，有限幅度平衡响度，不改变音高、语速，不剪内部停顿。派生切点与增益单独存证，真实组合重新评审，原生 `preserveSamples` 不再裁边。`--prefer-source` 用于明确优选已审查的同文上下文来源，`--prefer-whole` 保留完整录音；重新生成不复用旧哈希的合格结论。旧库备份留在仓库外，构建包只含 manifest 和被引用 WAV。

### 请求播报与接缝回归

房主统一播报自由积分收取请求发送，以及同意后的成交。服务返回单独的 `soundRequests` 最小摘要；个人 `paymentRequests` 待办仍只含与本人相关的请求，其他人的备注不会进入音频摘要，确认权限不扩大。一次同步跨过发送和同意时，先播请求，再播成交；刷新、重复轮询与普通玩家设备不补播。

浏览器显式维护一个活动语音，完成后取下一条，重复完成回调不能抢播。iPhone 使用 native busy 背压：忙时既不取下一句，也不响下一声铃。静音、切换及后台仍取消旧队列。


`refine_serena_edges.py` 从完整原录音回查不安全端点，在最多 60ms 邻域内仅移动到测得的低能量位置；没有可靠静音则保留该估计，继续检查或补录更长上下文。0.5ms（12 个采样）的独立端点包络消除硬波形跳变，保留长度及语音主体，不跨淡化字词、不改变音色和语速。实测超过 120ms 的低能量外部空白可缩短，仍保留 50ms 保护；原句内部发音不删除。修复音频均先输出暂存目录，实际运行路径拼接的完整句子重新听觉审查后采纳。

本轮修复后的开发库为 478 个上下文条目／482 个 WAV，4,391 项覆盖与 36 条完整播报审查通过；上面的 build 29 统计属于历史批次。build 30 已重新打包并安装至 iPhone 和 Mac arm64；现有旧版客户端不会自动下载新声音。

## 四端一致性与本次验证

- Android Mate 60 已实机试听男女声及 Serena；测试日志分别记录短句合成约 927ms、1213ms。这是本次两条日志，不是统计延迟，不包含首次模型加载，也不代表声学首声时刻。
- Android 语音模型在后台加载，开机不会运行 Qwen；选择保存在设备设置中，生成及播放通过同一队列串行进行。
- 桌面离线语音接口只允许服务设备上的房主调用；远程玩家不获得音色入口和合成权限，音频响应禁止缓存。素材和模型随客户端打包，不在游戏中下载。
- 本次桌面三音色均产生有效 WAV；Windows 安装与设备输出仍需在 Windows 主机验证，不能以 Mac 的结果代替。


## 暖语的当前组句优先级

- 已审核完整句优先，保持连续原录音；其次使用动作模板内明确审核过的前缀／金额配对；其余使用上下文动态规划，优先长片段以减少接缝。
- 金额和“分”尽量作为一个变量，变量从相同动作的完整句中提取。模板槽位找不到安全切点时保留完整句，不强行截断字头。
- 模板存在某个金额片段，不代表所有玩家和动作都可随意使用；`approvedPairs` 记录实际通过整句审核的组合。未知内容不改金额、不切换系统音色补读。
- 当前采用 792 条完整句配方、499 个上下文条目及模板配对，引用 1,223 个 WAV，约 120.0 MiB。2026-10-11 按平静、端正、中等而利落的标准更新 775 条录音／片段，并复核 602 个实际播放组合；这些是有限样本，任意变量组合未逐句人耳试听。后续普通话专项检查和来源见 [音频审核](TTS_AUDIO_REVIEW.md)。

## 当前播报术语

- Serena 暖语将德州“全下”读作英语 **All-in**；界面和结构化动作仍为“全下”，VITS 与系统音色保留中文。
- 语义清单保留中文键，manifest 的 `voiceTerminology` 记录实际发音；英文原词不按中文音译审核。
- 中文仍须自然标准普通话，英文 All-in 不意味着允许中文带偏外语口音。生成与复核增加中文声母、韵母和声调标准；人耳反馈优先于模型评分。
