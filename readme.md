# MeteorMasterDetecterAI

[![CI](https://github.com/mordom0404/Meteor-Master-Detecter-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/mordom0404/Meteor-Master-Detecter-AI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Build Windows onefile](https://github.com/mordom0404/Meteor-Master-Detecter-AI/actions/workflows/build-windows.yml/badge.svg)](https://github.com/mordom0404/Meteor-Master-Detecter-AI/actions/workflows/build-windows.yml)

内置的图像检测器（YOLOv8 → ONNX Runtime）。**当前版本：2.5.0**。

> **开源范围**：本仓库开源引擎代码（[MIT](LICENSE)），**不开源模型权重**。
> 引擎本身不含模型，运行时用 `--onnx_path` 指定；模型说明见 [docs/models.md](docs/models.md)。
> 更新记录见 [CHANGELOG.md](CHANGELOG.md)，参与贡献见 [CONTRIBUTING.md](CONTRIBUTING.md)。

支持两种运行模式：

- **一次性模式**（默认）：传入文件夹或文件列表，跑完即退出。适合离线批量分析。
- **监听模式**（`--watch_folder`，v2.4.0 新增）：常驻进程，模型只加载一次，文件夹里出现新文件自动识别。适合"实时监控"场景（直播、相机会话、自动出片流水线）。

---

# 安装 / 卸载（便携版）

从 [Releases](https://github.com/mordom0404/Meteor-Master-Detecter-AI/releases) 下载 `index.exe`（单文件，无需安装、无需管理员权限）：

1. 下载 `index.exe`，核对哈希：

   ```powershell
   Get-FileHash .\index.exe -Algorithm SHA256   # 与 Release 里的 index.exe.sha256 对比
   ```

2. 准备一个 ONNX 模型（本仓库不附带，见 [docs/models.md](docs/models.md)）。
3. 运行，例如：

   ```powershell
   .\index.exe --img_directory "D:\images" --onnx_path "D:\models\V8L_1.2.5.onnx"
   ```

**卸载 / 清理**：本程序不写注册表、不安装服务。删除 `index.exe`，再删除首次运行时解压出来的
缓存目录 `%LOCALAPPDATA%\MeteorMasterDetector\`（或 `{CACHE_DIR}\MeteorMasterDetector\`）即可。

---

# 目录

- [安装 / 卸载（便携版）](#安装--卸载便携版)
- [打包](#打包)
  - [打包 (mac)](#打包-mac)
  - [打包成单文件 (win)](#打包成单文件-win)
- [打包后的测试](#打包后的测试)
- [使用](#使用)
  - [示例](#示例)
  - [参数一览](#参数一览)
  - [一次性模式](#一次性模式)
  - [监听模式](#监听模式)
- [stdout 协议](#stdout-协议)
  - [共用：识别结果](#共用识别结果)
  - [监听模式独有：生命周期消息](#监听模式独有生命周期消息)
- [Python 环境安装](#python-环境安装)
- [从源码构建 / CI](#从源码构建--ci)
- [Code signing policy](#code-signing-policy)
- [更新日志](#更新日志)
- [许可证](#许可证)

---

# 打包

打包时请使用打包环境进行打包。

> 打包环境：Python **3.12**（`nuitka-patches` 锁定 Nuitka `2.7.13`，运行依赖 `python312.dll`）。
> 运行时依赖见 `requirements.txt`；打包环境的完整依赖快照见 `requirements-lock.txt`。

需要安装：

- `nuitka`
- `onnxruntime`
- `opencv-python`
- `pillow`
- `watchdog` （v2.4.0+ 监听模式依赖；不打监听模式可省，但建议保留）

## 打包 (mac)

推荐用仓库里的 `build_mac.py`（在装有依赖的 `MMAD-package` 环境里运行）：

```bash
conda activate MMAD-package
python build_mac.py
```

脚本用 `--standalone` 多文件分发（不是 `--onefile`），产物在 `dist/index.dist/`，
**可执行文件名固定为 `index.bin`** —— MMA 端 `utils-main/baseEngine.js` 里写死
`MeteorMasterDetecterAI: { entry: './index.bin' }`，改名会导致 spawn ENOENT，
表现为"监控启动失败"、退出码 -2。分发时需整体拷贝 `dist/index.dist/` 目录。

手写等价命令：

```bash
nuitka --standalone --lto=no --show-progress --output-dir=dist index.py
```

打包完成后记得删除 `libtk8.6.dylib` 文件（pillow 引入的），会导致审核不过。
（当前依赖版本下若未生成该文件，则无需处理。）

## 打包成单文件 (win)

打包时记得把系统 Path 变量里面的微信开发者工具删掉否则中文路径会报错。**推荐 MSVC**（VS 2022 BuildTools 自带的 cl.exe），仓库中的 `build.py` 已固定走 MSVC（不要加 `--mingw64`）。

```bash
nuitka --standalone --onefile --onefile-tempdir-spec="{CACHE_DIR}/MeteorMasterDetector/2.5.0-build1" --lto=no --show-progress --output-dir=dist index.py
```

`--standalone` 是后加的，以前不加好像也没有人反馈无法运行。

> ★ **Windows 商店版（APPX / MSIX）必须先打引导层补丁**：`build.py` 会在调用 Nuitka 之前自动执行
> `nuitka-patches/patch_onefile_bootstrap.py`。不打这个补丁，打包出来的 onefile 在商店版里
> 内部子进程会以 `0xC0000135`（STATUS_DLL_NOT_FOUND）秒退。详见 `nuitka-patches/README.md`。

`build.py` 和上面的命令均使用固定的用户缓存路径 `{CACHE_DIR}/MeteorMasterDetector/2.5.0-build1`。`{CACHE_DIR}` 由 Nuitka 在运行时解析；首次启动会解压，后续启动复用缓存，不再每次创建新的 `Temp/onefile_<PID>_<TIME>` 目录。缓存会在退出后保留，因此仍会占用解压后的磁盘空间。

发布新构建（包括依赖变化）时，请同步更新 `build.py` 和上述命令中的 `2.5.0-build1`，例如改成 `2.5.0-build2`，避免不同构建共用缓存。此设置需要重新打包才会生效；旧的 `onefile_*` 临时目录和旧版本缓存不会自动清理，可在确认相关程序全部退出后手动删除。缓存被删除后，下次启动会重新解压。

实际打包脚本里还会带上一堆 `--nofollow-import-to=` 排除 torch / ultralytics / scipy / matplotlib 等 `requirements.txt` 里"挂名"的包、 `--noinclude-data-files=` 排除 PIL 的字体文件、 `--include-data-files=` 把 `cv2/config*.py` 显式带进 bundle——这些一次性写在打包脚本里就行，readme 不展开。完整命令见 git history（最后一次成功的 build 命令）。

> ⚠️ 监听模式需要 `watchdog` 模块。如果在没装 watchdog 的环境里打包，会因为 `import watchdog` 失败直接报 ImportError。打包前请确认 `requirements.txt` 已安装（或在打包脚本里加 `--include-module=watchdog` / `--include-package=watchdog`，具体看 nuitka 版本）。

### 运行时依赖 vs 打包依赖

- `onnxruntime-directml`：Windows 上**必须装这个**（不是标准 `onnxruntime`，那个不带 DirectML EP）。它利用 DX12 调用任意 GPU（AMD / Intel / NVIDIA 都行）。打包出来的 exe 用 DML EP 推理，没有 DML 就 fallback 到 CPU。版本 ≥1.20 即可，本仓库当前用 `1.24.4`。
- `opencv-python`：标准包，注意 Nuitka onefile 模式 + cv2 有个老坑（`cv2/__init__.py` 的 bootstrap 会自递归），本仓库的 `index.py` 里有专门的 `_load_cv2_bypass()` 绕过，无需手动处理。
- `pillow`、`watchdog`：照装即可。

### 用 GitHub Actions 构建（发布 / 签名走这条路径）

仓库自带 [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml)：
在 GitHub 的 Windows runner 上从源码安装依赖 → 打 Nuitka 补丁 → 构建 `dist/index.exe`
→ 上传产物并生成 SHA256；打 `v*` tag 时还会自动创建 GitHub Release。

本地等价命令：

```bash
python build.py
```

> 申请免费代码签名证书时，"产物必须由公共 CI 从公开源码构建"是硬性条件，
> 所以正式发布请用这条路径，不要在本地手工打包后上传。签名接入见 [docs/signing.md](docs/signing.md)。

---

# 打包后的测试

## 一次性模式

```bash
./index.exe --img_directory "D:\images" --onnx_path "D:\models\V8L_1.2.5.onnx"
```

## 监听模式

```bash
./index.exe --watch_folder "D:\inbox" --onnx_path "D:\models\V8L_1.2.5.onnx"
```

启动后往 `test_inbox` 里拖 jpg，应该立即看到 stdout 输出一行 JSON。

---

# 使用

## 示例

下面所有示例都假设：

- 模型：`D:\models\V8L_1.2.5.onnx`（大模型，168MB，识别率更高）和 `D:\models\V8S_1.0.0.onnx`（小模型，44MB，速度更快）
- 测试图片：`D:\images\` （14 张 JPG，含流星、飞机、夜空等多种场景）

> 示例里的 `D:\images`、`D:\models` 只是占位路径，请替换成你自己的目录；模型不随仓库分发，见 [docs/models.md](docs/models.md)。

### 普通模式（一次性）

```bash
# 例 1: 最快速度批量识别整个 D:\images
./index.exe --img_directory "D:/images" --onnx_path "D:/models/V8L_1.2.5.onnx" --no_45 --force_CPU
```

```bash
# 例 2: 小模型 + 蒙版 + debug 把识别结果画到 <dir>/mmdebug/ 下
./index.exe --img_directory "D:/images" --onnx_path "D:/models/V8S_1.0.0.onnx" --mask "D:/mask.png" --debug
```

```bash
# 例 3: 用外部 JSON 文件列表（一般由 MMA 主程序生成，普通用户不需要）
./index.exe --img_directory_list "D:/images_list.json" --onnx_path "D:/models/V8L_1.2.5.onnx"
```

`img_directory_list.json` 文件结构示例：

```json
[
  {"preview": "D:/images/1372-extract.jpg", "id": "uuid-a", "filename": "1372-extract.jpg", "dir": "D:/images"},
  {"preview": "D:/images/xk1-1.jpg", "id": "uuid-b", "filename": "xk1-1.jpg", "dir": "D:/images"}
]
```

每跑完一张图，stdout 就输出一行 JSON（schema 见 [stdout 协议](#stdout-协议)），全部跑完后进程退出。

### 监听模式（v2.4.0+）

```bash
# 例 4: 基础监听 —— 监控 D:/images，新出现的 jpg 立即识别
./index.exe --watch_folder "D:/images" --onnx_path "D:/models/V8L_1.2.5.onnx" --no_45
```

启动后：

1. stdout 立刻输出 `{"type":"starting",...,"version":"2.5.0"}`（模型还没好）
2. 模型加载完输出 `{"type":"ready",...,"debounce_ms":300}`（可以开始处理了）
3. 往 `D:/images` 里复制 / 新建任何 jpg，约 300ms debounce 后 stdout 输出一行识别结果 JSON
4. 进程长驻直到 SIGTERM / SIGKILL

```bash
# 例 5: 监听 + 小模型 + 蒙版（直播 / 自动出片场景）
./index.exe --watch_folder "D:/images" --onnx_path "D:/models/V8S_1.0.0.onnx" --mask "D:/mask.png"
```

#### 手动测试监听模式（两个 PowerShell 窗口）

```powershell
# 窗口 A —— 启动引擎
cd D:\MMAD\dist\index.dist
.\index.exe --watch_folder "D:/images" --onnx_path "D:/models/V8L_1.2.5.onnx" --no_45 --force_CPU

# 窗口 B —— 模拟"新文件到达"
Copy-Item "D:\images\xk1-1.jpg" "D:\inbox\new_one_$(Get-Date -Format yyyyMMdd_HHmmss).jpg"
```

窗口 A 在 ~300ms 内会打印一行类似：

```json
{"outbox": [], "width": 1536, "height": 1024, "file": "D:\\inbox\\new_one_20260925_120700.jpg", "id": "5f8e3b...", "filename": "new_one_20260925_120700.jpg", "dir": "D:\\inbox"}
```

> 💡 `--watch_folder` 不会处理"启动前已存在"的文件。重启引擎时不会重新扫整个文件夹——只识别启动之后新出现的。如果你需要"补一遍历史"，用普通模式 `--img_directory`。

### Windows PowerShell 路径注意

PowerShell 默认所有字符串变量、单引号字面量不展开；路径含空格或中文时统一用双引号：

```powershell
# 正例
.\index.exe --watch_folder "D:\images" --onnx_path "D:\models\V8L_1.2.5.onnx" --no_45

# 错误：反斜杠在双引号里有时会被当作转义
.\index.exe --watch_folder "D:\images" --onnx_path "D:\models\V8L_1.2.5.onnx"  # OK
.\index.exe --watch_folder "C:\新建文件夹"  # OK
```

如果路径含特殊字符（比如 `$`），用单引号包整个 arg：

```powershell
.\index.exe --watch_folder 'U:\some$weird\path'
```

---

## 参数一览

| 参数 | 说明 | 模式 |
|------|------|------|
| `--mask <path>` | 蒙版 PNG 路径 | 共用 |
| `--img_directory <path>` | 要识别的图片文件夹（引擎内部 `os.walk` 递归） | 一次性 |
| `--img_directory_list <json>` | 图片列表的 JSON 文件路径 | 一次性 |
| `--watch_folder <path>` | 监控该文件夹，新出现的图片自动识别 | **监听** |
| `--onnx_path <path>` | onnx 模型路径 | 共用 |
| `--debug` | 识别结果画图，写到 `<dir>/mmdebug/<filename>` | 共用 |
| `--force_CPU` | 强制使用 CPU 推理（默认走 DML，没装 `onnxruntime-directml` 时也只剩 CPU） | 共用 |
| `--no_45` | 关闭 45° 旋转二次识别，提升速度 | 共用 |
| `--processed_log <path>` | 监听模式：每张图识别后**追加** basename 到这个文件（一行一个）。启动时读现有内容作 seed，重启不会重复识别历史文件 | 监听 |
| `--exclude_log <path>` | 监听模式：basename 列表（一行一个），里面命名的文件**永远跳过**（用户手动维护的"黑名单"），`#` 开头视为注释 | 监听 |

> ⚠️ `--watch_folder` 与 `--img_directory` / `--img_directory_list` **互斥**，同时传会 argparse 报错退出。`--processed_log` / `--exclude_log` 在一次性模式下被忽略（stderr 提示一次）。

## 一次性模式

行为：模型只加载一次 → 按顺序处理输入列表 → 全部完成 → 进程退出。

适用场景：离线分析已存在的图片文件夹（`--img_directory`），或者由外部（MMA 主程序）准备好文件列表（`--img_directory_list`，每项包含 `preview / id / filename / dir`）。

## 监听模式

行为：

1. 模型只加载一次，常驻内存
2. `watchdog.Observer` 监听文件夹（非递归）
3. 新文件落盘后等 **300ms debounce**（mtime 稳定窗口）再入队，避免读到半文件
4. worker 顺序从队列取文件，跑同一份 `_infer_single_file` 逻辑
5. 退出：SIGTERM / SIGKILL（MMA 端 `tree-kill`）。优雅退出（SIGTERM）会先把 pending 文件走完再 stop observer，发出 `{"type":"stopped"}` 消息；强杀（SIGKILL）跳过这一步，直接消失——这是预期行为，下次启动重新扫描即可。

适用场景：

- 相机连拍 / 直播录像自动入库
- 实时监控指定目录，新文件来了立即出识别结果
- 任何"长时间挂着、来一张处理一张"的场景

**扩展名限制**：watch_folder 模式只接受 `.jpg`（产品约定）。一次性 `--img_directory` 模式仍接受 `.jpg` / `.jpeg` / `.png` / `.bmp` 全套（兼容老的 json_list 输入）。

debounce 调优：`ImageStreamHandler.DEFAULT_DEBOUNCE_MS = 300`。RAW / HEIC 大文件（>50MB）或慢磁盘（NAS）建议拉到 800ms，改 `DEFAULT_DEBOUNCE_MS` 常量即可。

### 防重复识别：`--processed_log` + `--exclude_log`

监听模式有**三重去重**保护，引擎对"这张图我已经处理过"会自动跳过，节省 GPU 时间和噪声日志：

1. **TTL 内存缓存**（`--processed_recently_ttl`，默认 2s）：同一次会话内 watchdog 重复事件会被忽略。
2. **持久化日志**（`--processed_log <path>`）：每识别完一张图，把 basename **追加**到这个文件（一行一个）。下次启动时引擎读现有内容做 seed，重启后**不会重复识别**这些文件（即便它们还在文件夹里）。Tail 这个文件就能实时看到历史；想重跑历史就清空它。
3. **用户黑名单**（`--exclude_log <path>`）：basename 列表（一行一个，`#` 开头的行是注释）。这里命名的文件**永远跳过**，不推理、不写 processed_log。适合"这张图永远别分析"（比如测试废图、相机快门快照、隐私文件）。

匹配都是按 **basename**（不含路径）做的——watch_folder 是单文件夹目录，basename 在该文件夹内天然唯一。

```bash
# 例 6: 监听 + 持久化 processed_log + 用户黑名单（生产环境推荐配置）
./index.exe \
  --watch_folder "D:/inbox" \
  --onnx_path "D:/models/V8L_1.2.5.onnx" --no_45 \
  --processed_log "D:/processed.log" \
  --exclude_log "D:/exclude.txt"
```

`D:/exclude.txt` 内容示例：

```
# 相机测试废图
test_shutter_001.jpg
test_shutter_002.jpg
# 隐私
private_screenshot.jpg
```

`D:/processed.log` 启动前为空，每次启动后追加新的 basename。MMA 端可以 `Get-Content -Tail 5` 或类似方式实时查看。

> 💡 `processed_log` 和 `exclude_log` 都接受**不存在**的文件路径（启动时当空集合处理）；写失败（磁盘满 / 权限）只会 stderr 警告，**不会**中断 watcher。

---

# stdout 协议

引擎通过 stdout 输出**单行 JSON**（每行一条消息，`flush=True`）。MMA 主程序按行解析并转发为 IPC 事件。

## 共用：识别结果

每张图片识别完成一条，格式与 v2.3 之前的"一次性模式"**100% 一致**，MMA 渲染端不用改协议。

```json
{"outbox": [[x1, y1, x2, y2, score, class], ...], "width": 640, "height": 480, "file": "C:\\path\\IMG_0001.jpg", "id": "...", "filename": "IMG_0001.jpg", "dir": "C:\\path"}
```

字段：

- `outbox`：`[]` 表示没识别到目标；否则每个元素是 `[x1, y1, x2, y2, score, class]`
  - `class`：`0` 流星 / `1` 飞机 / `2` 精灵 / `3` 闪电
- `file`：图片绝对路径
- `id`：
  - 一次性模式下：来自输入 JSON 的 UUID（MMA 端用于匹配 imageList）
  - **监听模式下**：引擎自己生成的 `uuid.uuid4().hex`（每张图独立），MMA 端应该按 `file` 字段（绝对路径）匹配

## 监听模式独有：生命周期消息

| 消息 | 触发时机 | MMA 端建议处理 |
|------|---------|---------------|
| `{"type":"starting","folder":...,"version":"2.5.0"}` | 引擎启动、模型加载前 | 显示"加载模型中"，禁用"停止"按钮（避免模型未加载完被打断） |
| `{"type":"ready","folder":...,"version":"2.5.0","debounce_ms":300,"exclude_log":N,"processed_log_seed":M}` | 模型加载完 + Observer 启动完 | 解锁"启动监控"按钮 / 显示"监控中"状态。`exclude_log` / `processed_log_seed` 是 v2.4.0 这次新增的字段，显示各自 seed 了多少个 basename（启动时历史跳过数） |
| `{"type":"backfill_enqueued","count":N,"skipped_existing":K}` | **启动时**：扫到 folder 里已有 `count` 张图片待补跑，开始补跑；另有 `skipped_existing` 张被持久化日志 / 用户黑名单跳过。`count + skipped_existing = 文件夹里总图片数` | 显示"补跑历史 0/N"，进入历史回放状态 |
| `{"type":"backfill_complete","count":N}` | **启动时**：N 张历史图片全部识别完 | UI 切到"实时监控"模式 |
| `{"type":"error","file":...,"id":...,"msg":"..."}` | 单文件识别失败（EXIF 损坏、onnx 报错等） | 记录日志，**继续处理后续** |
| `{"type":"stopped"}` | 优雅退出（SIGTERM 路径） | 进程退出信号；不一定每次都能拿到（树杀模式下跳过） |

`backfill_enqueued` 和 `backfill_complete` 是 v2.4.0+ 新增的事件，用来标记**启动时的历史补跑**阶段。MMA 渲染端可以借此把"历史回放进度"和"实时监控"做成两种 UI 状态，避免用户看到一堆老结果以为是新文件到达。

历史回放的输出顺序与原 `--img_directory` 一致（按文件名升序），保证确定性。

watchdog 缺失时的错误（在 `runWatchFolder` 启动时检测）：

```json
{"type":"error","msg":"watchdog 库未安装。请在 conda 环境 (MMAD-Package) 中执行: pip install watchdog"}
```

非监听模式错误：

```json
{"type":"error","msg":"watch_folder 不存在或不是目录: ..."}
```

---

# Python 环境安装

- 按照 yolov8 官方文档直接在 conda 中安装环境，onnxruntime 不需要装 gpu 版本
- 要额外装一下 `onnxruntime_directml`，这个库利用 win 的 DX12 来调用显卡，兼容性好
- 监听模式额外需要 `watchdog>=4.0,<7.0`：`pip install watchdog`

完整的运行时依赖见 `requirements.txt`（已精简为引擎真正需要的包：numpy / opencv-python / pillow / watchdog / onnxruntime-directml）。打包环境的完整依赖快照（含 torch / ultralytics 等只有训练/导出才用的包）在 `requirements-lock.txt`，需要复现已发布构建时用它。

---

# 从源码构建 / CI

## 本地构建

需要 Python 3.12 + MSVC（VS 2022 BuildTools 的 `cl.exe`）：

```bash
pip install -r requirements.txt
pip install nuitka==2.7.13
python build.py
```

产物为 `dist/index.exe`，构建报告（commit / 依赖版本 / SHA256）写到 `build_report.txt`。

## GitHub Actions

- [`ci.yml`](.github/workflows/ci.yml)：push / PR 时做语法检查和 CLI 冒烟测试（不需要模型）；
- [`build-windows.yml`](.github/workflows/build-windows.yml)：在 Windows runner 上从源码构建
  `index.exe`，上传产物 + SHA256；打 `v*` tag 时自动创建 Release。

## 发布流程（签名要求）

1. 更新 `index.py` 的 `VERSION` 和 `CHANGELOG.md`；
2. 打 tag（如 `v2.5.0`）并 push；
3. `build-windows.yml` 依次执行：构建 → `upload-artifact`（未签名）→（已启用时）SignPath 签名 →
   重新计算 SHA256 → 发布 Release；
4. 用 `Get-AuthenticodeSignature` 与 SHA256 校验后再分发（见 [docs/signing.md](docs/signing.md)）。

> 在 SignPath 申请通过之前，Release 里的 exe 是**未签名**的——这正好满足
> SignPath「必须先发布过要签名的形态」的前置条件。

---

# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).

- **Authors / Committers and Reviewers**: [@mordom0404](https://github.com/mordom0404) (repository owner)
- **Approvers**: [@mordom0404](https://github.com/mordom0404) (repository owner)
- Every release is built from this repository on GitHub-hosted runners by
  [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml),
  uploaded as a GitHub Actions artifact, and **manually approved** for signing.
- **Privacy**: This program will not transfer any information to other networked systems unless
  specifically requested by the user or the person installing or operating it.
  It does not ship any model weights; the ONNX model file is supplied by the user
  (see [docs/models.md](docs/models.md)) and is not part of this project or its signed artifacts.
- **Uninstall**: delete `index.exe` and the cache directory `%LOCALAPPDATA%\MeteorMasterDetector\`
  (see [安装 / 卸载（便携版）](#安装--卸载便携版)).

> 中文摘要：本项目通过 SignPath Foundation 的免费 OSS 代码签名计划签署 Release 产物；
> 签名只针对由 GitHub Actions 从本仓库源码构建的 `index.exe`，模型权重不在签名范围。
> 签名接入与校验方法见 [docs/signing.md](docs/signing.md)。

---

# 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

> 注：宿主程序侧的引擎版本字段与本项目保持一致，跨版本升级时记得一起 bump。

---

# 许可证

- 代码：[MIT](LICENSE) —— 可自由使用、修改、商用，保留版权声明即可；
- 模型权重：**不在开源范围内**，不随仓库分发，权利由模型作者保留（见 [docs/models.md](docs/models.md)）。

第三方依赖的许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
