# 代码签名与发布（Windows，onedir）

本项目从 v2.6.0 起**默认发布 onedir 形态**：产物是 `index.dist/` 目录（`index.exe` + 依赖 DLL），
代码签名只针对目录内的 **`index.dist/index.exe`**。

签名渠道有两种用法：

- **本地签名**（自有/付费证书，`scripts/sign_index.ps1` + signtool）；
- **CI 签名**（SignPath Foundation 免费 OSS 证书，产物由 GitHub Actions 构建后提交签名）。

> 状态：SignPath 尚未接入。本文是申请条件、接入方式与校验说明。

## 1. 为什么是 SignPath Foundation

| 渠道 | 是否免费 | 能否签 Windows exe | 备注 |
|------|----------|--------------------|------|
| **SignPath Foundation** | ✅ 免费 | ✅ | 要求公开仓库 + 全部组件 OSI 许可 + GitHub Actions 构建 + 人工审批 |
| Certum Open Source | 中国区有条件免费 / €49 起 | ✅ | 仅限**非商业**分发；免费档要求 GitHub >1k star |
| Azure Artifact Signing | ❌ 约 $9.99/月 | ✅ | 个人开发者仅限美国/加拿大 |
| 微软商店（MSIX） | ✅ 商店重签 | ✅ | 走商店分发时最省事，零 SmartScreen 警告 |

如果本项目后续要**商业分发**，请走付费 OV/EV 证书或微软商店，不要用 OSS 免费档
（Certum 会因商业用途吊销，SignPath 也不接受商业双许可的组件）。

## 2. 申请前必须满足的条件

- [ ] 仓库 **Public**，使用 OSI 认证许可证（本项目为 [MIT](../LICENSE)）；
- [ ] 仓库内**没有专有组件**：模型权重（`.onnx` 等）不入库、不入产物、不放进 Release 资产；
- [ ] 已有**未签名的正式 Release**（onedir zip + SHA256，非 draft）；
- [ ] 产物由 **GitHub Actions（GitHub 托管 runner）** 从本仓库源码构建；
- [ ] `index.exe` 带 product name / version 元数据（`build.py` 已设置）；
- [ ] `readme.md` 有 **Code signing policy** 小节（含 SignPath 指定原句、角色、隐私声明）；
- [ ] 维护者 GitHub 账号开启 2FA，SignPath 账号也要开 MFA；
- [ ] 有一定「可验证的声誉」：SignPath 明确要求可执行程序有下载/引用记录，
      新建仓库建议先发 1–2 个未签名 Release、积累 Star / 下载量再申请。

## 3. 申请与接入流程（SignPath）

1. 在 <https://signpath.org/apply> 提交申请（仓库 URL、许可证、Release、构建 workflow、
   Code signing policy 链接、团队角色、隐私声明）。
2. 等待人工审核（不承诺时限，通常数周），按邮件要求补材料。
3. 通过后：
   - 安装 SignPath GitHub App：<https://github.com/apps/signpath>；
   - 在 SignPath 控制台创建 Organization / Project / Signing Policy / Artifact Configuration；
   - 邀请自己为 Approver，开启 MFA。
4. 在 GitHub 仓库 Settings → Secrets and variables 里配置：

   | 名称 | 类型 | 内容 |
   |------|------|------|
   | `SIGNPATH_API_TOKEN` | Secret | SignPath 控制台生成的 API token |
   | `SIGNPATH_ORG_ID` | Secret | SignPath organization id |
   | `SIGNPATH_PROJECT_SLUG` | Variable | 项目 slug |
   | `SIGNPATH_SIGNING_POLICY_SLUG` | Variable | 签名策略 slug，例如 `release-signing` |
   | `SIGNPATH_ENABLED` | Variable | 设为 `true` 才启用签名步骤 |

5. Artifact configuration（onedir：签名 zip 内的 `index.dist/index.exe`）。下面为示意，
   实际路径/语法以 SignPath 控制台生成的模板为准：

   ```xml
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file path="MeteorMasterDetecterAI-2.6.0-win-onedir.zip">
       <pe-file path="index.dist/index.exe">
         <authenticode-sign description="MeteorMasterDetecterAI"
                            description-url="https://github.com/mordom0404/Meteor-Master-Detecter-AI"/>
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

   > 只签 `index.dist/index.exe`。目录里的 python312.dll / onnxruntime.dll / cv2.pyd 等
   > 是上游 OSS 二进制，不要重签；它们随目录一起分发，签名不影响其可用性。

## 4. 本地签名（signtool，onedir）

自有/付费证书或内部测试证书可用 `scripts/sign_index.ps1` 直接签名：

```powershell
# 1) 构建 onedir + zip
python build.py --mode onedir --zip

# 2) 签名（证书存储 thumbprint / PFX 文件二选一）
.\scripts\sign_index.ps1 -Thumbprint "ABCDEF0123456789..." -Zip
.\scripts\sign_index.ps1 -PfxPath "D:\certs\codesign.pfx" -PfxPassword "***" -Zip
```

脚本动作：

1. `signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com`（时间戳 URL 可用
   `-TimestampUrl` 改；`-NoTimestamp` 关闭）；
2. `Get-AuthenticodeSignature` 校验 `Status = Valid`；
3. 重算 `index.dist/index.exe.sha256`（签名后哈希会变）；
4. `-Zip` 时重新打 `MeteorMasterDetecterAI-<版本>-win-onedir.zip` 并重算 zip 哈希。

> 签名必须发生在**打包之后**；签名后再修改/替换 `index.exe` 会让签名失效。
> 如需签名多个文件，请分别签名，不要对整个目录做任何「加壳/合并」。

## 5. CI 签名（SignPath，发布推荐）

`.github/workflows/build-windows.yml` 的顺序：

```
python build.py --mode onedir --zip
  → upload-artifact（未签名 zip，拿到 artifact-id）
  → [SignPath 签名，SIGNPATH_ENABLED=true 时] 签 zip 内的 index.dist/index.exe
  → 解压签名产物并校验 Get-AuthenticodeSignature
  → 重算 index.exe 与 zip 的 SHA256（签名会改变哈希！）
  → 发 Release（zip + sha256 + THIRD_PARTY_LICENSES.txt）
```

关键点：

- 未签名产物**必须先 `actions/upload-artifact`**，SignPath 只接受 GitHub artifact 的 id；
- 所有 job 必须跑在 GitHub 托管 runner 上（`windows-2022`），不能用自建 runner；
- **签名后必须重算 zip/exe 的 SHA256**，否则 Release 里的哈希对不上；
- 每次 Release 的签名请求需要 Approver 在 SignPath 控制台人工批准。

## 6. 校验签名

```powershell
Expand-Archive .\MeteorMasterDetecterAI-2.6.0-win-onedir.zip -DestinationPath .\verify -Force

# 签名状态：Status 应为 Valid
Get-AuthenticodeSignature .\verify\index.dist\index.exe |
  Format-List Status, StatusMessage, SignerCertificate

# 版本资源
(Get-Item .\verify\index.dist\index.exe).VersionInfo |
  Format-List ProductName, ProductVersion, FileVersion

# 与 Release 里的 SHA256 对比
(Get-FileHash .\MeteorMasterDetecterAI-2.6.0-win-onedir.zip -Algorithm SHA256).Hash.ToLower()
```

签名通过后，Windows 属性页会显示签名者。但注意：**签名 ≠ 立刻没有 SmartScreen 警告**，
SmartScreen 还看下载历史；持续发布、把误报提交 <https://www.microsoft.com/wdsi> 可以加速建立声誉。

## 7. 模型与签名边界（重要）

- 签名对象只有 `index.dist/index.exe`；**模型权重不在签名范围**；
- 不要把 `.onnx` 打进产物、放进 zip/MSIX/MSI，或者作为同一个 Release 的附件同一批上传。
  模型由用户通过 `--onnx_path` 指定，或由单独渠道分发。详见 [docs/models.md](models.md)；
- README 已说明「引擎是通用 ONNX 推理器，任何人都可以按文档导出自己的模型」，
  这是通过 SignPath「项目不含专有组件」审核的关键表述，不要删除。

## 8. 集成进 MeteorMaster 时的注意事项

- 宿主程序应把**整个 `index.dist/` 目录**作为资源打包/spawn，entry 指向 `index.dist/index.exe`；
  不要只拷贝 exe，也不要在集成时重命名 exe；
- 启动前可用 `index.exe --version` 校验引擎版本，用 `Get-AuthenticodeSignature` 校验发布者；
- 升级时**整目录替换**（先停进程，再删旧目录/覆盖），避免新旧 DLL 混用；
- 签名后的 exe 不要做任何二进制修改（包括资源编辑、压缩壳），否则签名失效。

## 9. 如果被拒

SignPath 明确表示「没有必须接受项目的义务」。被拒不是终局：

- 先继续发 1–2 个版本、积累下载与 Star，过 1–3 个月重新申请；
- 或者换付费 OV 证书（$99–300/年）；
- 或者走微软商店 MSIX（商店免费重签、无 SmartScreen 警告）。
