# SignPath 申请前：测试与配置清单

> 目标：把仓库、构建流水线、产物和账号都调到 SignPath Foundation 能直接通过审核/签名的状态。
> 申请入口：<https://signpath.org/apply>；条款：<https://signpath.org/terms.html>。

## 0. 当前差距（2026-11-12 自查）

| 项 | 现状 | 需要做 |
|---|---|---|
| 仓库 Public | ❌ 仍为 Private | 清理/发布准备完成后切 Public |
| GitHub Release | ❌ 还没有 tag / Release | 打 `v2.6.1` tag，由 CI 产出未签名 Release |
| Actions 全绿 | ⚠️ 未知（新 workflow 首次实跑） | 在 Actions 页确认 `CI` 与 `Build Windows (onedir)` 均成功 |
| 仓库 2FA | ⚠️ 需确认 | GitHub Settings → Password and authentication |
| License 识别 | ✅ MIT（`LICENSE` 已就位） | 公开后确认侧栏显示 MIT |
| Code signing policy | ✅ README 已含指定原句/角色/隐私/卸载 | 发布页（Release 说明）也链接到它 |
| exe 版本资源 | ✅ ProductName/ProductVersion/FileVersion | 用 `scripts/verify_release.ps1` 每次发版自检 |
| 模型边界 | ✅ 不入库、不入 zip、不同 Release | 每次发版跑校验脚本确认 zip 里无 `.onnx` |
| 签名产物形态 | ✅ onedir zip（`index.dist/`） | 确认 SignPath Artifact Configuration 与 zip/目录结构匹配 |
| SignPath 账号 / GitHub App | ❌ 未注册 | 见 §3、§4 |

## 1. 申请前必须完成的仓库配置

- [ ] 仓库 **Public**（SignPath 只审公开项目）；
- [ ] 根目录 `LICENSE` = MIT，GitHub 侧栏识别为 MIT license；
- [ ] README 含 **Code signing policy**（SignPath 指定原句 + Authors/Reviewers/Approvers + 隐私声明）；
- [ ] README 说明：引擎是通用 ONNX 推理器，模型由用户提供，**Release 不含模型**；
- [ ] 至少 1 个**非 draft 的未签名 Release**（onedir zip + zip/exe 的 SHA256 + 第三方许可清单）；
- [ ] GitHub 账号开启 **2FA**；
- [ ] 仓库 Settings → Security：开启 **Secret scanning + Push protection**、Dependabot、CodeQL、
      Private vulnerability reporting；
- [ ] 仓库描述 / Topics / 默认分支（`master`）正确；
- [ ] 确认没有自建 runner、没有需要人工触发才能构建的旁路（SignPath 校验 origin 必须来自 GitHub workflow）。

## 2. 构建与测试（本仓库）

### 2.1 CI 测试

```powershell
# 本地等价（CI 也是跑这些）
python -m unittest discover -s tests -v
python -m py_compile index.py build.py
```

- [ ] `CI` workflow 在 push/PR 上全绿；
- [ ] `Build Windows (onedir)` 手动触发或 tag 触发成功，产物包含：
      `dist/index.dist/index.exe`、`dist/index.dist/index.exe.sha256`、
      `MeteorMasterDetecterAI-<版本>-win-onedir.zip` 及其 `.sha256`；
- [ ] 下载 CI artifact 后在本地解压、跑一次 `index.exe --version` / `--licenses`。

### 2.2 产物自检（每次发版/签名前必跑）

```powershell
python build.py --mode onedir --zip
.\scripts\verify_release.ps1
```

脚本检查：zip 布局、`index.dist/index.exe`、版本资源、`--version`、`--licenses`、
`index.exe.sha256`、zip 哈希、**zip 内无模型权重**。任一项失败即退出非 0，可直接放进 CI。

### 2.3 二进制兼容性测试矩阵（签名前至少跑一遍）

| 场景 | 期望 |
|------|------|
| 干净 Windows 11（无 Python/conda/VC++ 运行库） | `index.exe` 能启动，`--version` 正常 |
| 干净 Windows 10 22H2（同上） | 同上 |
| 非管理员用户 / 中文用户名 / 含空格路径 | 正常识别，缓存/日志路径可写 |
| 中文/空格/UNC（`\\server\share\...`）图片路径 | 正常读出并输出 JSON |
| 一次性模式：`--img_directory` | 每图一行 JSON，进程退出码 0 |
| 一次性模式：`--img_directory_list` | 同上 |
| 监听模式：`--watch_folder` + 新文件 | `starting`/`ready` 后输出结果；SIGTERM 优雅退出 |
| `--mask` / `--debug` | 蒙版生效；`mmdebug/` 生成标注图 |
| 默认（不做 `--no_45`） | 无目标时会走 45° 旋转二次检测，结果坐标正确 |
| GPU（DirectML）/ `--force_CPU` | 两种 provider 都能推理，结果合理 |
| 断网环境 | 不依赖网络（无模型下载、无遥测） |
| 从 zip 解压后直接运行 | 不依赖安装，DLL 齐全 |

### 2.4 签名冒烟测试（申请前先本地验证 signtool 链路）

用自签测试证书验证签名工具链（**不要**用生产证书做测试）：

```powershell
# 生成一个 1 天有效的自签测试证书（CurrentUser\My）
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=MMAD Test Signing" `
  -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddDays(1)
$cert.Thumbprint

# 签名（自签证书没有可信时间戳，用 -NoTimestamp）
.\scripts\sign_index.ps1 -Thumbprint $cert.Thumbprint -NoTimestamp
```

预期：

- `signtool` 成功；
- `Get-AuthenticodeSignature` 的 **Status = UnknownError**（自签根不受信任，属预期）；
- `index.exe` 仍能运行、`--version` 正常；
- `index.dist/index.exe.sha256` 已更新为新哈希。

测试完删除测试证书：

```powershell
Remove-Item "Cert:\CurrentUser\My\$($cert.Thumbprint)"
```

> 正式签名（SignPath 或付费证书）在**打包完成后**执行；签完不要再改 exe。
> 用 `-Zip` 重新打 zip 并更新 zip/exe 哈希。

### 2.5 签名后的验收（拿到正式签名后）

```powershell
.\scripts\sign_index.ps1 -Zip    # 用正式证书/或 SignPath 产物
.\scripts\verify_release.ps1     # 布局/版本/哈希/无模型
Get-AuthenticodeSignature .\dist\index.dist\index.exe |
  Format-List Status, StatusMessage, SignerCertificate
```

- [ ] Status = Valid，签名者正确（SignPath = `SignPath Foundation`）；
- [ ] 时间戳存在；
- [ ] zip / exe 哈希与 Release 一致；
- [ ] 在干净 VM 上运行一次，SmartScreen 不再提示「未知发布者」（首次下载仍可能需要声誉积累）。

## 3. SignPath 账号与项目配置（通过审核后）

- [ ] 安装 [SignPath GitHub App](https://github.com/apps/signpath)；
- [ ] SignPath 控制台创建 **Organization / Project / Signing Policy / Artifact Configuration**；
- [ ] GitHub 仓库 Secrets/Variables：

  | 名称 | 类型 | 用途 |
  |------|------|------|
  | `SIGNPATH_API_TOKEN` | Secret | 调用 SignPath API |
  | `SIGNPATH_ORG_ID` | Secret | organization id |
  | `SIGNPATH_PROJECT_SLUG` | Variable | 项目 slug |
  | `SIGNPATH_SIGNING_POLICY_SLUG` | Variable | 签名策略 slug |
  | `SIGNPATH_ENABLED` | Variable | `true` 才启用签名步骤 |

- [ ] 开启所有成员 MFA；配置 Authors / Reviewers / Approvers（单人项目至少把自己设为 Approver）；
- [ ] 在 Signing Policy 里开启 **强制校验 product name / version**（我们的 exe 已带版本资源）；
- [ ] 建议开启 pipeline policies：`required_github_hosted`、`disallow_reruns`、
      对 `v*` tag 的 ruleset 保护。

### Artifact Configuration（onedir）

当前 workflow 上传的是 `MeteorMasterDetecterAI-<版本>-win-onedir.zip`（一个文件），
所以配置需要按 zip 内路径匹配（注意文件名带版本号）：

```xml
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <zip-file path="MeteorMasterDetecterAI-<版本>-win-onedir.zip">
    <pe-file path="index.dist/index.exe">
      <authenticode-sign description="MeteorMasterDetecterAI"
                         description-url="https://github.com/mordom0404/Meteor-Master-Detecter-AI"/>
    </pe-file>
  </zip-file>
</artifact-configuration>
```

> 版本号变化会改变 zip 文件名。两个方案：
> ① 在 SignPath 控制台按版本更新 path（最直接）；
> ② 改 workflow：artifact 上传 `dist/index.dist/` 目录而不是 zip，配置写成
> `<pe-file path="index.exe">`，签名后再由 workflow 重新打 zip（更稳定，但需要调整 workflow）。
> 建议申请时直接问 SignPath 支持哪种更合适，再定稿。

## 4. 申请与审核

1. 完成 §1–§2，确认 CI 全绿、Release 已发；
2. 在 <https://signpath.org/apply> 提交：仓库 URL、许可证、Release 链接、构建 workflow、
   Code signing policy 链接、团队角色、隐私声明、待签产物（`index.dist/index.exe`）；
3. 等待审核（不承诺时限，通常数周）；按邮件补材料；
4. 通过后按 §3 配置，设置 `SIGNPATH_ENABLED=true`，打 tag 验证一次「构建 → 签名 → 发布」闭环。

## 5. 常见拒签/失败原因（提前规避）

| 原因 | 规避 |
|------|------|
| 项目太新、无可验证声誉 | 先发 1–2 个 Release、积累下载/Star 后再申请 |
| 仓库含专有组件 | 模型不入库/不入 zip/不进 Release；`verify_release.ps1` 每次校验 |
| 产物不是 CI 构建 | 只用 `build-windows.yml` 的产物提交签名，不用本地手工包 |
| exe 缺版本资源 | `build.py` 已设置；签名策略开启强制校验后不通过会直接报错 |
| 签名后哈希没更新 | workflow 已在签名后重算 zip/exe 哈希；`sign_index.ps1` 同样处理 |
| 自建 runner / 跳过 upload-artifact | 保持 `windows-2022` 托管 runner，不绕过 artifact 步骤 |
| 商业分发 | 不要用 OSS 免费档；走付费 OV/EV 或微软商店 |
