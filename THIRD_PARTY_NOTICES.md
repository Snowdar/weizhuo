# 第三方与素材说明

根目录《围桌非商业与非赌博用途许可证 v1.0》适用于原创代码、文档及作者有权许可的随附素材，不替换或限制第三方组件自身的许可证。

| 组件 | 版本 | 用途 | 许可证 |
| --- | --- | --- | --- |
| python-qrcode | 8.2 | 二维码编码 | `weizhuo/vendor/qrcode-8.2.dist-info/LICENSE`（BSD，含原始代码许可说明） |
| PyPNG | 0.20220715.0 | PNG 输出 | `weizhuo/vendor/pypng-0.20220715.0.dist-info/LICENCE`（MIT），`weizhuo/vendor/png.py` 也保留正文 |

依赖以源码随项目分发，保留版权和许可。`weizhuo/vendor/bin/` 为本机安装脚本，不纳入仓库。

`weizhuo/static/assets/` 展示素材 通过 GPT Image 生成，记录见目录中的 `ASSETS.md`，随项目按根目录许可证提供。AI 来源不意味着素材独占或第三方权利担保。根目录个人预览图和邀请二维码不属于分发内容。

桌面构建使用 [PyInstaller](https://github.com/pyinstaller/pyinstaller) 6.16.0（GPL 与 bootloader 分发例外）。分发包包含 Python / Tcl / Tk 运行时的许可文本与 PyInstaller 许可；二维码与 PyPNG 原始许可也随资源保留。Pillow 仅用于构建图标转换，不作为桌面运行依赖。移动工程使用 BeeWare Briefcase 与 Toga，构建时下载对应平台运行时；发布移动包时须保留其依赖许可。

## 可选 iOS 离线神经语音

sherpa-onnx 推理引擎采用 Apache-2.0，项目：<https://github.com/k2-fsa/sherpa-onnx>。iOS 测试构建使用 1.13.8 的共享框架（内含 ONNX Runtime），具体许可证见上游分发与 ONNX Runtime 仓库；保留上游声明。

可选音色模型为 `sherpa-onnx-vits-zh-ll`，来源：<https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/vits.html>。模型包 README 仅说明社区贡献及 VITS-fast-fine-tuning 训练来源，未提供完整音色/训练数据授权；尚不作为已确认许可的公开发布资产。维护者决定将当前 FP16 模型、词典与正式 Serena 音频随 `resources/voice/` 提供，二进制推理框架仍在构建时准备。此决定不补齐上游授权，也不能用引擎 Apache-2.0 推断模型许可。 2026-10-11 的具体核查见 [VITS 许可核查](docs/VITS_LICENSE_REVIEW.md)。

## 系统语音与 Serena 预制片段

- 清晰使用 iOS 的 AVSpeechSynthesizer 与设备已安装的系统音色。项目不分发 Apple 的音色文件，也不向云端发送播报文本。
- 暖语是开发阶段使用 Qwen3-TTS 的内置 Serena 音色生成的预制 WAV；不是真人声音克隆，手机不运行或携带 Qwen 的 1.7B 模型。
- 原始模型为 [Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)，上游模型卡标注 Apache-2.0，Serena 属于其内置音色。开发使用 [mlx-community 的 4bit 转换版](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit)，本地模型卡同样标注 Apache-2.0；生成工具为 mlx-audio。模型许可不等于对所有生成内容的权利担保。
- 整句生成、提示词、文本清单、评审与采纳方法保留在 `weizhuo/mobile/serena_templates.py`、`review_serena.py` 和 `adopt_serena.py`，资源清单记录在生成的 `manifest.json`。已采纳的正式预制音频随 `resources/voice/Serena/` 入库，生成大模型、原句候选及开发缓存不入库；公共分发说明必须明确实际包含的资源，保留对应上游许可和声明。

四音色的编号映射、实机测量范围、FP16 存储与构建步骤见 [离线播报说明](docs/OFFLINE_VOICE.md)。项目的非商用许可不改变 Apache 等第三方组件的许可。

## TTS 来源索引与复现环境

| 资源或工具 | 来源与许可依据 | 围桌中的使用方式 |
| --- | --- | --- |
| sherpa-onnx 1.13.8 | [源码](https://github.com/k2-fsa/sherpa-onnx)、[Apache-2.0 许可](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE) | 可选 iOS 推理框架；下载 URL 与 SHA-256 固定在 `weizhuo/mobile/ios/voice/assets.json`。 |
| ONNX Runtime | [源码与 MIT 许可](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) | sherpa iOS 分发内的推理依赖；实际二进制版本及声明需按该框架分发包核对。 |
| VITS zh-ll | [模型目录及试听](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/vits.html#vits-zh-ll-chinese-7-speakers)、[训练项目](https://github.com/Plachtaa/VITS-fast-fine-tuning) | sid=1 男声、sid=2 女声；模型 README 没有完整音色/训练数据授权。引擎许可不涵盖这项缺口。 |
| Qwen3-TTS CustomVoice / Serena | [官方模型卡](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)、[源码](https://github.com/QwenLM/Qwen3-TTS)、[技术报告](https://arxiv.org/abs/2601.15621) | 仅开发时离线生成固定片段，模型卡标注 Apache-2.0；手机播放生成的 WAV，不运行 Qwen；当前完整句子与上下文拼接库及审查范围见 [音频评审](docs/TTS_AUDIO_REVIEW.md)。 |
| MLX 4bit 转换模型 | [mlx-community 模型卡](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit) | Apple Silicon 开发环境的本地转换模型，来源仍为 Qwen CustomVoice；保留原始模型声明。 |
| mlx-audio 0.5.7 | [源码](https://github.com/Blaizzy/mlx-audio)、[MIT 许可](https://github.com/Blaizzy/mlx-audio/blob/main/LICENSE) | 开发阶段生成工具，不作为手机运行依赖。固定开发依赖见 `requirements-serena.txt`。 |
| Apple 系统语音 | [AVSpeechSynthesizer](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer) | 使用设备已安装音色，不提取或转发 Apple 音色文件。 |

核对日期：2026-10-07。实际播放策略、编号映射、质量门槛和测量边界见 [离线播报说明](docs/OFFLINE_VOICE.md)。生成提示与处理代码由仓库保存；不把预制片段称作实时 Qwen 合成，也不将第三方内置音色称作项目原创声音。

正式 FP16 VITS 和 Serena 资源已在 `resources/voice/` 随仓库提供；`.voice-assets/` 是忽略的本地构建副本，推理框架另行准备。构建者配置可选资源时，应保留原始模型卡、许可证、NOTICE 及其依赖声明；公开安装包前逐项核对所包含的资产，授权尚未确认的 VITS 模型不能标注为已获公共分发许可。默认无权重构建可使用系统语音。生成音频的来源说明与代码许可证分别管理，不能仅用本项目许可证替代上游声明。

Android 离线播报新增使用官方 sherpa-onnx 1.13.8 AAR（SHA-256 `633c24321e06b1fe79feafa03ea16cbc0f8a286641e2da3559bac91bdb13bd96`）、ONNX Runtime 及 Kotlin 标准库 2.1.0；均按各自上游 Apache-2.0 条款保留通知。桌面端使用 sherpa-onnx 1.13.8 Python/原生运行库及 NumPy 2.3.3（BSD-3-Clause），复用同一 VITS 模型及 Serena 资源；模型训练数据与音色资源的授权限制仍遵循上文，接入更多平台不改变授权状态。
