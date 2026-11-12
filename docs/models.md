# 模型说明（为什么模型不在仓库里）

本仓库开源的是**推理引擎代码**，许可证为 MIT（见 [LICENSE](../LICENSE)）。
**模型权重不在开源范围内**，也不随仓库分发：

- `*.onnx` / `*.pt` / `*.pth` 已在 `.gitignore` 中排除，不要提交到仓库；
- 模型文件不是 MIT 许可的一部分，模型作者保留全部权利；
- 引擎本身不含任何模型，必须通过 `--onnx_path` 指定模型文件才能运行。

## 当前使用的模型

| 模型 | 大小 | SHA256 | 说明 |
|------|------|--------|------|
| `V8L_1.2.5.onnx` | ≈168 MB | `A8E6CAE69E88ACAB572AFCCC6884528BF0A9F272BBCE1A155DDEC09548197D49` | 大模型，识别率更高 |
| `V8S_1.0.0.onnx` | ≈44 MB | `23FAC5C8EC70BAB02ED6CFF724D18DB49B505934775A6B14A2D324E48CB2149C` | 小模型，速度更快 |

模型由作者单独分发（随宿主程序内置或联系作者获取），本仓库不提供公开下载链接。

校验下载到的模型（PowerShell）：

```powershell
Get-FileHash .\V8L_1.2.5.onnx -Algorithm SHA256
```

## 用自己的模型

引擎只依赖 ONNX，不依赖 ultralytics。想用自己训练的模型，按下面流程导出即可。

1. 训练一个 YOLOv8 检测模型（4 类）。
2. **类别顺序必须和引擎一致**，否则识别结果会张冠李戴。引擎内固定为（`index.py` 的 `CLASSES`）：

   ```python
   CLASSES = ["meteor", "plane", "sprite", "lightning"]   # 0 流星 / 1 飞机 / 2 精灵 / 3 闪电
   ```

   即训练数据的 `data.yaml` 里 `names` 必须按这个顺序排列。
3. 导出 ONNX：

   ```bash
   pip install ultralytics
   yolo export model=best.pt format=onnx opset=12 simplify=True
   ```

   本项目也用过动态输入尺寸的导出（`V8L_1.2.5_dynamic.onnx`）。如果图片尺寸不固定，
   导出时加 `dynamic=True`；引擎会按模型实际输入尺寸做 letterbox / resize。
4. 运行：

   ```bash
   python index.py --img_directory "D:/images" --onnx_path "D:/models/my_model.onnx" --no_45
   ```

## 模型数据的权利

- 训练数据（夜空 / 流星照片等）的版权归各自作者所有，不在本仓库开源范围内；
- 如果你要基于本项目分发自己的模型，请自行确认训练数据与权重的许可。
