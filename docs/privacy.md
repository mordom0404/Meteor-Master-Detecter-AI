# 隐私说明 / Privacy Policy

MeteorMasterDetecterAI（`index.exe`）是一个**离线**的图像推理引擎。

- 本程序**不联网**：不包含遥测、统计上报、账户系统、自动更新或模型下载功能；
- 只处理用户通过命令行参数指定的本地文件（图片、ONNX 模型、mask、日志）；
- 推理结果只写到 **stdout**（一行一条 JSON），调试图写到用户指定目录下的 `mmdebug/`，
  不会上传到任何服务器；
- 不收集个人数据，不读取与任务无关的用户目录；
- 第三方组件的许可信息见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

如果宿主程序（如 MeteorMaster）在调用本引擎之外还处理其他数据，请以宿主程序自己的隐私政策
为准；本引擎本身不传输任何信息。

> This program will not transfer any information to other networked systems unless
> specifically requested by the user or the person installing or operating it.
