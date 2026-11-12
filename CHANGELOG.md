# 更新日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.6.0] - 2026-11-12

### 新增
- **默认打包形态改为 onedir**：`build.py --mode onedir` 产出 `dist/index.dist/`（`index.exe` + 依赖 DLL），
  可直接集成进 MeteorMaster；`--zip` 额外产出 `MeteorMasterDetecterAI-<版本>-win-onedir.zip`，
  并自动生成 `index.exe.sha256` / zip 的 `.sha256`。
- `build.py --mode onefile` 保留旧单文件形态（默认不再是 onefile）。
- 新增 `scripts/sign_index.ps1`：用 signtool 对 `index.dist/index.exe` 签名、校验签名、重算 SHA256，
  可选重新打 zip（签名后哈希会变化）。
- 新增 `docs/integration.md`：onedir 目录如何集成进 MeteorMaster（布局、版本检查、协议、升级）。
- 开源准备：`LICENSE`（MIT）、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、
  `THIRD_PARTY_NOTICES.md`、`docs/models.md`、`docs/signing.md`。
- CLI 新增 `--version`（打印版本后退出）与 `--licenses`（打印第三方组件许可，离线可用）。
- GitHub Actions：`ci.yml`（语法检查 + CLI 冒烟测试）、`build-windows.yml`
  （从源码构建 onedir、打 zip、上传产物、生成 SHA256、tag 自动发 Release）。
- 打包产物写入 Windows 版本资源（product name / version），并把
  `THIRD_PARTY_NOTICES.md` 打进产物；`build.py` 额外输出 `build/nuitka-report.xml`。

### 变更
- `build.py`：onefile 模式才应用 `nuitka-patches` 的 MSIX/APPX 引导层补丁；onedir 自动跳过。
- `build.py` 的构建报告增加「打包形态」、目录总大小、zip 哈希。
- `requirements.txt` 精简为引擎真正的运行时依赖；新增 `requirements-lock.txt`
  （打包环境完整快照）。Windows 明确使用 `onnxruntime-directml`。
- `build.py` 不再写死本机 Python 路径（默认当前解释器，可用 `MMAD_BUILD_PYTHON` 覆盖），
  版本号与 `BUILD_TAG` 从 `index.py` 推导。
- 文档中的本机绝对路径改为通用示例路径。

### 安全 / 合规
- **重写 `index.py` 中与 Ultralytics 官方 ONNXRuntime 示例高度同构的部分**，确保 MIT 授权成立：
  删除从未被调用的 `draw_detections`；重写 `postprocess`（解码、NMS、角点切换）与类/`__init__`
  的 docstring 与注释；`preprocess` 尾部注释一并改写。行为保持不变——已用两张模型
  （V8L_1.2.5 / V8S_1.0.0）、15 张测试图、一次性与 45° 旋转两条路径，对比改写前后 stdout
  逐行一致。
- `THIRD_PARTY_NOTICES.md` 增加「代码来源说明」，并为 Nuitka 补丁中的上游锚点片段补充署名。

### 移除
- 不再跟踪 `nuitka-crash-report.xml`、`report.xml` 等构建报告。

## [2.5.0] - 2026-10

### 修复
- ★ 修复 Windows 商店版（APPX / MSIX）照片识别启动即退的问题：onefile 引导层改为用
  内部子进程的**真实物理路径**启动（`GetFinalPathNameByHandleW`），绕开包文件虚拟化造成的
  「DLL 搜索路径与文件实际位置错位」。修复前内部子进程以 `0xC0000135`
  （STATUS_DLL_NOT_FOUND）退出（找不到 `python312.dll`），修复后正常识别。
- 补丁本体在 `nuitka-patches/`，由 `build.py` 在打包前自动应用；锁定 Nuitka 版本
  （2.7.13），命中不上预期源码结构直接失败，不会静默漏打。

### 变更
- 构建标识升为 `2.5.0-build1`（与旧 `2.4.0-build1` 缓存隔离，旧缓存不会被误用）。
- 打包脚本 `build..py` 更名为 `build.py`，不再写死本机 Python 路径
  （默认用当前解释器，可用 `MMAD_BUILD_PYTHON` 覆盖）。

### 不变
- 识别算法、模型、CLI 参数与 JSON 行输出协议均未变更。

## [2.4.0] - 2026-09

### 新增
- 新增 `--watch_folder` 长驻监听模式：模型只加载一次，文件夹出现新文件自动识别，
  启动时还会扫一遍历史做 backfill。
- 新增 `--processed_log <path>`：持久化已识别列表，basename 一行一个，重启不会重复识别。
- 新增 `--exclude_log <path>`：用户维护的 basename 黑名单（`#` 注释），永远跳过
  （兼容 PowerShell `Out-File utf8` 的 BOM）。

### 变更
- `YOLOv8.__init__` provider 列表改为白名单（DML + CPU），不再打印
  `available_providers` 噪声误导（之前会把 TensorRT / CUDA 等"装了但用不了"的 EP 也打出来）。
- cv2 bootstrap 自递归的 onefile 兼容问题通过 `_load_cv2_bypass()` 跳过
  `cv2/__init__.py` 直接加载 `cv2.pyd`。
- 编译目标从 CUDA onnxruntime-gpu（145MB）切到 `onnxruntime-directml`（60MB）。
- watch_folder 扩展名只接受 `.jpg`（产品约定）；一次性模式仍接受
  `.jpg/.jpeg/.png/.bmp` 全套。

## [2.3.x] - 2026

- 一次性模式，与 v2.2.0 相同的 JSON schema；增加飞行方向判断后的坐标交换算法。

## [2.2.0] - 2026

- 早期一次性模式（`baseline.py:1 VERSION = "2.2.0"`）；增加图片方向（EXIF Orientation）检查，
  解决竖屏图片识别错误。
