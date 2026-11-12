# SignPath Foundation 申请表（逐字段填写稿）

> 申请页：<https://signpath.org/apply>（表单在页面内嵌 iframe 里，需在浏览器打开）
> 我无法代你点提交（需要你的真实姓名/邮箱并勾选同意条款），但下面**每个字段都给出了可直接粘贴的值**。
> 官方项目要求与流程见 [signpath-readiness.md](signpath-readiness.md)。

## 0. 提交前 1 分钟自查

- [ ] 浏览器打开 <https://signpath.org/apply>（VPN 正常）；
- [ ] 已确认 [Release v2.6.1](https://github.com/mordom0404/Meteor-Master-Detecter-AI/releases/tag/v2.6.1) 页面底部有
      `Free code signing provided by SignPath.io, certificate by SignPath Foundation.`（已加好）；
- [ ] 隐私说明页可访问：<https://github.com/mordom0404/Meteor-Master-Detecter-AI/blob/master/docs/privacy.md>；
- [ ] GitHub 账号 2FA 已开（提交后审核会看）。

## 1. 表单字段值（直接复制）

| 字段 | 填什么 |
|---|---|
| **Project Name** * | `MeteorMasterDetecterAI` |
| **Repository URL** * | `https://github.com/mordom0404/Meteor-Master-Detecter-AI` |
| **Homepage URL** * | `https://github.com/mordom0404/Meteor-Master-Detecter-AI` |
| **Download URL** * | `https://github.com/mordom0404/Meteor-Master-Detecter-AI/releases/tag/v2.6.1` |
| **Privacy Policy URL** * | `https://github.com/mordom0404/Meteor-Master-Detecter-AI/blob/master/docs/privacy.md` |
| **Wikipedia URL** (optional) | 留空 |
| **Tagline** * | `Offline YOLOv8 → ONNX Runtime engine for detecting meteors, planes, sprites and lightning in night-sky images.` |
| **Category** * | `Science`（该项目分类列表：Accessibility / Audio / Developer tools / Educational / Gaming / Graphics / Productivity / Science / Other；天文图像检测选 Science 最贴切） |
| **Description** * | 见下方 A 段 |
| **Reputation** * | 见下方 B 段（按实际情况选一个版本） |
| **Maintainer Type** | `Individual`（单人维护；若下拉里没有，选最接近的 Community/Other） |
| **Build System** * | `GitHub`（即 GitHub Actions；我们的构建 workflow 在 `.github/workflows/build-windows.yml`） |
| **First Name** * / **Last Name** * | 你的真实姓名（英文或拼音） |
| **Email** * | 你的常用邮箱（SignPath 账号与审核通知会用） |
| **Company Name** (optional) | 留空（个人项目） |
| **Primary Discovery Channel** * | 如实选（例如 `Search engine`；如果不确定选 Other 并在下一栏说明） |
| **Please specify the exact source** (optional) | 例如 `Google search: "free code signing for open source Windows exe"`（如实填写即可） |
| 复选框 | 勾选：同意 Code of Conduct、同意证书以 SignPath Foundation 名义签发、同意接收沟通、同意存储个人数据（按你的偏好决定第三项） |

## 2. 长文本模板

### A. Description（直接粘贴）

```
MeteorMasterDetecterAI is an MIT-licensed, offline inference engine that runs YOLOv8-derived
ONNX detection models with ONNX Runtime (DirectML or CPU) to detect meteors, aircraft, sprites,
and lightning in night-sky photographs. It provides a command-line interface and a
line-delimited JSON protocol so host applications can batch-analyze image folders or watch a
directory for new images in real time. The engine is a standalone Windows component (onedir
distribution) used by the MeteorMaster desktop application. It does not ship any model weights:
the ONNX model is supplied by the user at runtime and is not part of the open-source repository
or the signed artifacts. The project is built and released entirely on GitHub-hosted runners
via GitHub Actions.
```

### B. Reputation（二选一，按真实情况改）

**B1（保守/如实，推荐先提交这个）**

```
Publicly released under the MIT license in November 2026. The project has a complete CI/CD
pipeline on GitHub-hosted runners (unit tests, onedir build, artifact hashing and a published
release: https://github.com/mordom0404/Meteor-Master-Detecter-AI/releases/tag/v2.6.1).
The engine has been shipped as the inference component of the MeteorMaster desktop application
(v2.5–v2.6.x). The public repository is newly published and currently early-stage (0 stars).
```

**B2（如果你有更多可验证材料，在 B1 基础上补充）**

```
Additional evidence:
- Build/release workflow: https://github.com/mordom0404/Meteor-Master-Detecter-AI/actions
- MeteorMaster (host application) listing/download page: <填公开链接>
- Related community posts / tutorials: <填链接>
- Download counts: <填 GitHub Releases download 数或商店统计>
```

> ⚠️ SignPath 对可执行程序的「声誉」是**自由裁量**的软门槛。如实写、附链接即可；如果这次被拒，
> 继续发 1–2 个版本、积累下载后再重提（被拒不等于永久拒绝）。

## 3. 提交后会怎样

1. 审核（不承诺时限，通常数周，可能邮件补材料）；
2. 通过后你会收到 SignPath 邀请：
   - 安装 SignPath GitHub App：<https://github.com/apps/signpath>；
   - 在 SignPath 控制台建 Organization / Project / Signing Policy / Artifact Configuration；
   - 开启 MFA，把自己设为 Approver；
3. 在 GitHub 仓库配 Secrets/Variables（`SIGNPATH_API_TOKEN`、`SIGNPATH_ORG_ID`、
   `SIGNPATH_PROJECT_SLUG`、`SIGNPATH_SIGNING_POLICY_SLUG`、`SIGNPATH_ENABLED`）；
4. 打下一个版本 tag，验证「构建 → 上传 artifact → 签名 → 重算哈希 → Release」；
5. 下载产物执行 `Get-AuthenticodeSignature .\index.dist\index.exe`（应为 `Valid`，
   签名者 `SignPath Foundation`）。

## 4. 可能被追问的问题与回答

| 问题 | 建议回答 |
|---|---|
| 项目里是否包含闭源组件？ | 否。仓库与产物均不含模型权重；模型由用户通过 `--onnx_path` 提供（见 docs/models.md）。 |
| 为什么要签名？ | 以 onedir 形式分发 Windows 程序，希望用户能看到可验证的发布者，并防止下载/升级过程被篡改。 |
| 谁是 Approver？ | 目前仅我一人维护（@mordom0404），我同时担任 Author / Reviewer / Approver，并已开启 MFA。 |
| 构建是否可验证？ | 全部由 GitHub Actions 在 GitHub 托管 runner（windows-2022）上构建，先 `upload-artifact` 再提交签名。 |
| 是否有商业分发？ | 引擎本身是 MIT 开源、免费；宿主程序 MeteorMaster 的商业模式请如实说明（如果涉及售卖，SignPath 仍可能接受，但不要用 Certum 免费档）。 |

## 5. 提交按钮

确认以上字段后，点表单最下方 **Submit**。如果提交成功，SignPath 会发确认邮件；
把邮件/页面截图发我，我可以继续帮你做后续的 Artifact Configuration 和 workflow 签名接线。
