# VITS zh-ll 许可核查

核查日期：2026-10-11。对象为围桌当前使用的 `sherpa-onnx-vits-zh-ll`，不是所有 VITS 模型。

## 核查结果

- 模型托管仓库：https://huggingface.co/csukuangfj/sherpa-onnx-vits-zh-ll
- 核查时 revision：`7ddf37bcacf05ed56afee360d96835be633a5265`。
- 模型卡仅说明社区贡献及使用 VITS-fast-fine-tuning 训练；没有许可声明。
- Hugging Face 模型 API 的 `cardData` 为 null，tags 没有 license 字段；当前文件列表没有 LICENSE / NOTICE 等模型许可文件。
- 官方使用文档提供下载和运行方法，但对应条目没有模型权重再分发许可说明：https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/vits.html
- 训练工具 VITS-fast-fine-tuning 的代码采用 Apache-2.0：https://github.com/Plachtaa/VITS-fast-fine-tuning/blob/main/LICENSE 。这不能单独证明由社区另行训练并上传的 zh-ll 权重也采用同一许可。
- 本地构建资源 README 与上游模型卡一致；当前资源未附完整模型、音色与训练数据许可。

## 结论与复现边界

- 结论是“尚未确认模型权重的再分发许可”，不是“已发现明确禁止”，也不据此断言侵权。
- 围桌的非商业许可、免费分发和来源署名不能代替上游授权。
- 核查时原 Git 不包含模型权重；维护者随后明确决定随仓库提供当前 FP16 模型，原许可核查结论不变。`provision_voice.py` 和 `ios/voice/assets.json` 提供上游 URL 与固定 SHA-256，供构建者获取相同输入。下载入口不等于授权声明。
- 已有本地安装包包含模型；公开 Release 与本地构建是不同交付步骤，应明确随包资源的许可状态。
- 要确认该模型权重的再分发授权，仍需要提供者补充适用的许可／再分发声明，并说明适用范围。没有证据时不替上游添加 Apache-2.0 标签。
- 未经用户授权，不向上游发送消息或创建 Issue。若后续取得声明，保留原文链接、日期、revision 和对应模型哈希，再同步第三方说明与打包清单。
