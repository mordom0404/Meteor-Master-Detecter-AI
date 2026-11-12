# 参与贡献

感谢你愿意帮忙！这个仓库是「流星检测引擎」的推理部分，主要目标只有一个：
**稳定、可预测地跑完一批图片 / 持续监听文件夹，并把结果按行 JSON 输出给宿主程序**。
接口的兼容性比新功能更重要。

## 开发环境

- Windows 10/11（主要目标平台；macOS 可打包但不是主要测试平台）
- Python 3.12（打包环境为 3.12.11；`nuitka-patches` 锁定 Nuitka 2.7.13，依赖 `python312.dll`）
- 依赖安装：

  ```bash
  pip install -r requirements.txt
  ```

- 运行测试（不需要模型、不需要显卡）：

  ```bash
  python -m unittest discover -s tests -v
  ```

- 本地打包（Windows，需要 MSVC / VS 2022 BuildTools）：

  ```bash
  python build.py
  ```

## 可以提交什么

- 🐛 Bug 修复：尤其是路径、EXIF、并发、Nuitka 打包相关的问题；
- 📝 文档修正（readme / docs）；
- 🧪 测试用例（不需要模型即可验证的行为）；
- ⚡ 性能优化（请附上前后对比数据）。

## 不接受的内容

- ❌ 模型权重（`.onnx` / `.pt` 等）——仓库不托管模型，见 [docs/models.md](docs/models.md)；
- ❌ 训练数据、私人照片、含个人信息或本机绝对路径的日志；
- ❌ 破坏 stdout 行 JSON 协议的改动（宿主程序依赖这个协议）；
- ❌ 无意义的格式化大 diff（会把 git blame 弄乱）。

## 代码约定

- 保持单文件 `index.py`：Nuitka 打包和宿主程序调用都依赖这个入口，拆分模块需先讨论；
- stdout **只**输出一行一条 JSON；诊断信息走 stderr；
- 涉及 CLI 参数 / JSON 字段的改动，必须同步更新 `readme.md`，并考虑向后兼容；
- 新增依赖前先说明理由，优先用标准库和已有依赖。

## 提交 PR

1. Fork 并新建分支（`fix/xxx`、`feat/xxx`）；
2. 跑通 `python -m unittest discover -s tests -v`；
3. 说明改动动机、影响范围、如何验证；
4. 涉及行为的改动请附复现步骤或截图。

提交即表示你同意以本仓库的 [MIT 许可证](LICENSE) 授权你的贡献。
