# 代码签名与发布（Windows）

本项目计划通过 **SignPath Foundation** 的免费 OSS 代码签名服务，给 Release 里的
`index.exe` 做 Authenticode 签名，避免用户看到「未知发布者」。

> 状态：**尚未接入**。本文是申请通过后的接入说明与提前准备清单。
> SignPath 的免费签名只覆盖「开源项目」，证书签发给 **SignPath Foundation**，
> 用户看到的发布者会是 `SignPath Foundation` 而不是作者本人。

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
- [ ] 仓库内**没有专有组件**：模型权重（`.onnx` 等）不入库、不入 exe、不放进 Release 资产；
- [ ] 已有**未签名的正式 Release**（exe + SHA256，非 draft）；
- [ ] 产物由 **GitHub Actions（GitHub 托管 runner）** 从本仓库源码构建；
- [ ] `index.exe` 带 product name / version 元数据（`build.py` 已设置）；
- [ ] `readme.md` 有 **Code signing policy** 小节（含 SignPath 指定原句、角色、隐私声明）；
- [ ] 维护者 GitHub 账号开启 2FA，SignPath 账号也要开 MFA；
- [ ] 有一定「可验证的声誉」：SignPath 明确要求可执行程序有下载/引用记录，
      新建仓库建议先发 1–2 个未签名 Release、积累 Star / 下载量再申请。

## 3. 申请流程

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

5. Artifact configuration（SignPath 控制台里粘贴）：

   ```xml
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <pe-file path="index.exe">
       <authenticode-sign description="MeteorMasterDetecterAI"
                          description-url="https://github.com/mordom0404/Meteor-Master-Detecter-AI"/>
     </pe-file>
   </artifact-configuration>
   ```

## 4. 接入方式（已预留在 workflow 里）

`.github/workflows/build-windows.yml` 的顺序是：

```
构建 index.exe → upload-artifact（拿到 artifact-id）
  → [SignPath 签名，SIGNPATH_ENABLED=true 时]
  → 复制签名产物回 dist/index.exe
  → 重新计算 SHA256（签名会改变哈希！）
  → 发 Release
```

关键点：

- 未签名产物**必须先 `actions/upload-artifact`**，SignPath 只接受 GitHub artifact 的 id；
- 所有 job 必须跑在 GitHub 托管 runner 上（`windows-2022`），不能用自建 runner；
- **签名后必须重新计算 SHA256**，否则 Release 里的哈希对不上；
- 每次 Release 的签名请求需要 Approver 在 SignPath 控制台人工批准。

## 5. 校验签名

```powershell
# 签名状态：Status 应为 Valid
Get-AuthenticodeSignature .\index.exe | Format-List Status, StatusMessage, SignerCertificate

# 版本资源
(Get-Item .\index.exe).VersionInfo | Format-List ProductName, ProductVersion, FileVersion

# 与 Release 里的 SHA256 对比
(Get-FileHash .\index.exe -Algorithm SHA256).Hash.ToLower()
```

签名通过后，Windows 属性页会显示 `SignPath Foundation`。但注意：
**签名 ≠ 立刻没有 SmartScreen 警告**，SmartScreen 还看下载历史；持续发布、
把误报提交 <https://www.microsoft.com/wdsi> 可以加速建立声誉。

## 6. 模型与签名边界（重要）

- 签名对象只有 `index.exe`；**模型权重不在签名范围**。
- 不要把 `.onnx` 打进 exe、放进 MSIX/MSI，或者作为同一个 Release 的附件同一批上传。
  模型由用户通过 `--onnx_path` 指定，或由单独渠道分发。详见
  [docs/models.md](models.md)。
- README 已说明「引擎是通用 ONNX 推理器，任何人都可以按文档导出自己的模型」，
  这是通过 SignPath「项目不含专有组件」审核的关键表述，不要删除。

## 7. 如果被拒

SignPath 明确表示「没有必须接受项目的义务」。被拒不是终局：

- 先继续发 1–2 个版本、积累下载与 Star，过 1–3 个月重新申请；
- 或者换付费 OV 证书（$99–300/年）；
- 或者走微软商店 MSIX（商店免费重签、无 SmartScreen 警告）。
