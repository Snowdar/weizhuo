# 正式离线播报资源

- `voice/model.onnx`：当前已实机采纳的 VITS zh-ll FP16 权重，约 58 MiB；不含重复的 FP32 模型。
- `voice/Serena/`：正式 manifest 和 1,223 个已采纳／被引用 WAV；无需下载 Qwen 或重新生成，保留当前接缝与音色。
- `voice/dict/`、词典和 FST：随上游模型的分词及文字、数字处理资源；上游原始 README 保留。
- `voice/files.sha256.json`：逐文件大小与 SHA-256，构建准备会验证；修改正式库时同步更新，不收集候选、旧库、API 密钥或用户数据。
- 在仓库根运行 `python3 weizhuo/mobile/provision_voice.py --platform desktop`，将资源校验并准备到本地构建目录；Android 改为 `android`，iPhone 改为 `ios`。仅平台运行库可能需要联网下载。
- 已有本地 Voice 不会被覆盖；要复现仓库版本，请在干净克隆中准备。克隆本仓库会取得约 192 MiB 语音资源；应用运行时不下载模型。
- VITS 模型的明确权重／音色再分发许可仍未找到。本次按维护者明确决定随仓库提供，不表示确认获得上游授权，不将其套用围桌自有许可或标注为 Apache-2.0。见 [核查记录](../docs/VITS_LICENSE_REVIEW.md)。
- Serena 是 Qwen3-TTS 内置音色的生成音频，不包含 Qwen 模型权重。上游来源、工具和许可边界见 [第三方说明](../THIRD_PARTY_NOTICES.md)。
- 纯 Python `server.py` 启动入口当前仍未加载离线播报适配器；现有桌面 App 仅允许服务设备本机房主调用 VITS／Serena。跨设备扫码房主使用浏览器系统语音。这是当前功能限制，不因为资源入库而自动改变。
