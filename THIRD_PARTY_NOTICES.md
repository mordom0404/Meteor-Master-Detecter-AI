# Third-Party Notices / 第三方组件许可

本项目的 `index.exe`（Nuitka onefile）会把下列第三方组件以二进制形式打进单个 exe 再分发，
因此需要保留它们的版权声明与许可信息。仓库代码本身以 [MIT](LICENSE) 发布。

- 完整许可文本：随 Release 附件 `THIRD_PARTY_LICENSES.txt` 一起分发（CI 自动生成），
  也可以直接查看各项目仓库中的 LICENSE。
- 离线用户可运行 `index.exe --licenses` 查看本文件（已打进 exe）。
- 如果 exe 里实际打包的组件与本表不一致，以 `build/nuitka-report.xml`（构建报告）为准。

## 随 exe 分发的组件

| 组件 | 版本 | 许可证 | 项目 |
|------|------|--------|------|
| Python 运行时 | 3.12.11 | PSF-2.0 | https://www.python.org |
| Nuitka（onefile 引导层 / 运行时） | 2.7.13 | Apache-2.0 | https://nuitka.net || ONNX Runtime / onnxruntime-directml | 1.24.4 | MIT | https://github.com/microsoft/onnxruntime |
| DirectML.dll（Microsoft） | 随 onnxruntime-directml | Microsoft 可再分发条款 | https://learn.microsoft.com/windows/ai/directml/ |
| OpenCV（opencv-python） | 4.10.0.84 | Apache-2.0（OpenCV 本体）/ MIT（Python wrapper） | https://opencv.org |
| FFmpeg（OpenCV wheel 内含） | 随 opencv-python | LGPL-2.1+（按发行版配置） | https://ffmpeg.org |
| Pillow | 12.0.0 | HPND | https://python-pillow.org |
| NumPy | 2.2.0 | BSD-3-Clause | https://numpy.org |
| watchdog | 4.0.2 | Apache-2.0 | https://github.com/gorakhargosh/watchdog |
| protobuf | 6.32.0 | BSD-3-Clause | https://github.com/protocolbuffers/protobuf |
| flatbuffers | 25.2.10 | Apache-2.0 | https://github.com/google/flatbuffers |
| coloredlogs | 15.0.1 | MIT | https://github.com/xolox/python-coloredlogs |
| humanfriendly | 10.0 | MIT | https://github.com/xolox/python-humanfriendly |
| packaging / typing_extensions / six / filelock 等传递依赖 | 见 lock 文件 | Apache-2.0 / PSF-2.0 / MIT / Unlicense | 各自 PyPI 页面 |

> Nuitka 当前固定 `2.7.13`（Apache-2.0）。注意 Nuitka 4.x 起 PyPI 元数据改为
> AGPLv3+（带链接例外），升级 Nuitka 前必须重新评估本文件与分发方式。

## 代码来源说明

`index.py` 中「模型输出解码 / 检测框后处理」这部分接口与算法思路参考了
Ultralytics YOLOv8 ONNXRuntime 官方示例（AGPL-3.0）。当前仓库中的实现是**独立重写的表达**
（自查：与上游无连续 3 行以上相同代码、无逐字 docstring/注释），不包含其源代码；
本仓库整体以 [MIT](LICENSE) 发布。

`nuitka-patches/patch_onefile_bootstrap.py` 中的三处锚点字符串逐字摘自
Nuitka 2.7.13（Apache-2.0，Copyright 2025 Kay Hayen and others），只用于在构建时定位
Nuitka 源码中的修改位置；本仓库不包含 Nuitka 本体。

## 仅构建/训练/导出使用，不随 exe 分发

以下包只用于构建、测试或训练/导出模型，已被 `build.py` 的
`--nofollow-import-to=` 排除，**不进入分发的 exe**：

- **ultralytics / ultralytics-thop（AGPL-3.0）** —— 只用来训练 YOLOv8 并导出 ONNX；
  引擎运行时不 import 它们。若你要自己导出模型，请自行遵守 AGPL-3.0。
- torch / torchvision（BSD-3-Clause）、scipy（BSD-3-Clause）、
  matplotlib（PSF-based）、sympy（BSD-3-Clause）、polars（MIT）、
  pyinstaller（GPL-2.0-with-exception，仅实验用）。

## 微软可再分发二进制

`onnxruntime-directml` wheel 内含 `DirectML.dll` 与 MSVC 运行库，属于 Microsoft
可再分发组件；分发时不要删除其版权信息，也不要把本项目说成是 Microsoft 的官方产品。

## 生成完整许可文本（维护者）

```bash
pip install pip-licenses
pip-licenses --format=plain-vertical --with-license-file --with-urls \
  --output-file=THIRD_PARTY_LICENSES.txt
```

CI 在每次 Windows 构建时会自动生成该文件并作为 Release 附件上传。

## 商标

OpenCV、ONNX Runtime、Microsoft、DirectML、Nuitka、Python 等名称与商标归各自所有者所有。
本项目与上述项目的维护方没有隶属或背书关系。
