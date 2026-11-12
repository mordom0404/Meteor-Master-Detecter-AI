# 集成进 MeteorMaster（宿主程序）

本项目从 v2.6.0 起以 **onedir** 形态发布：一个 `index.dist/` 目录，入口是
`index.dist/index.exe`，旁边是 Python 运行时、onnxruntime、OpenCV 等依赖 DLL。

## 1. 目录布局

```
<MeteorMaster 资源目录>/
  engine/
    index.dist/
      index.exe          ← 签名对象（入口）
      index.exe.sha256
      python312.dll
      onnxruntime.dll / DirectML.dll
      cv2/ ... PIL/ ... 等依赖
```

- 把**整个 `index.dist/` 目录**一起打包/安装，**不要只拷 `index.exe`**；
- 目录名建议保持 `index.dist`，exe 名必须是 `index.exe`（宿主侧 entry 指向它）；
- 签名只覆盖 `index.dist/index.exe`；升级时整目录替换，避免新旧 DLL 混用。

## 2. 启动方式

```powershell
$engine = Join-Path $PSScriptRoot "engine\index.dist\index.exe"
Start-Process -FilePath $engine -ArgumentList @(
    "--img_directory", "D:\images",
    "--onnx_path", "D:\models\V8L_1.2.5.onnx",
    "--no_45"
) -NoNewWindow -Wait
```

- 监听模式用 `--watch_folder <dir>`，通过 SIGTERM 停止；托管侧建议收 stdout 行 JSON、stderr 当日志。
- **stdout 协议**：每行一条 JSON（识别结果 / 生命周期消息），schema 见 readme「stdout 协议」。
- 模型不随引擎分发，由宿主或用户通过 `--onnx_path` 提供（见 [models.md](models.md)）。

## 3. 版本检查

```powershell
$version = & "engine\index.dist\index.exe" --version   # 输出形如 "index.exe 2.6.0"
```

宿主侧建议在启动前比对最低引擎版本，避免旧引擎不兼容新参数/JSON 字段。
`index.py` 顶部的 `VERSION` 是唯一版本来源，宿主侧的引擎版本字段应与它保持一致。

## 4. 签名校验（可选但推荐）

```powershell
$sig = Get-AuthenticodeSignature "engine\index.dist\index.exe"
if ($sig.Status -ne "Valid") { throw "引擎签名无效: $($sig.StatusMessage)" }
```

发布版的 SHA256 记录在 `index.dist/index.exe.sha256`（签名后生成）。若宿主自己做完整性校验，
注意**签名后的哈希与构建时的哈希不同**，以签名后的清单为准。

## 5. 升级流程

1. 停掉正在运行的引擎进程（监听模式走 SIGTERM 优雅退出）；
2. 用新版本 `index.dist/` 整体替换旧目录（可先改名为 `index.dist.old` 再切换）；
3. 启动新引擎，用 `--version` 确认版本；
4. 首次启动可跑一次 `--img_directory` 小样本冒烟，确认 JSON 输出正常。

## 6. 与商店版（MSIX）的关系

- onefile 形态在 MSIX/APPX 下需要 `nuitka-patches` 的引导层补丁（见 `nuitka-patches/README.md`）；
- **onedir 形态不经过 onefile 引导层，不需要该补丁**，目录直接由宿主安装包分发即可；
- 如果宿主最终走微软商店，商店会对 MSIX 包统一重签，引擎 exe 的签名仍建议保留。
