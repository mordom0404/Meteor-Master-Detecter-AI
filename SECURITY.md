# 安全策略

## 支持的版本

| 版本 | 是否维护 |
|------|----------|
| 2.5.x | ✅ 是 |
| < 2.5 | ❌ 否（请升级到最新版） |

## 报告安全问题

请**不要**在公开 issue 里贴漏洞细节、模型文件、私人照片或带本机路径的日志。

推荐通过 GitHub 的私密报告入口：

> 仓库页面 → **Security** → **Report a vulnerability**
> （GitHub Security Advisories，只有维护者能看到）

如果该入口不可用，可以开一个不含细节的 issue 说明"有安全问题需要私下沟通"，维护者会联系你。

我们会在确认问题后尽快修复，并在 Release Notes 里致谢（如果你愿意署名）。

## 重点关注的范围

- 引擎处理不可信输入时的健壮性：畸形 JPEG / EXIF、超大图片、UNC / 中文 / 空格路径；
- `--img_directory_list` 传入的 JSON、`--processed_log` / `--exclude_log` 的文件内容；
- 监听模式下的路径处理与并发（文件写入未完成时被读取）；
- 发布产物：exe 的签名与 SHA256 是否一致、模型文件的校验；
- 依赖项的已知漏洞（Dependabot 会跟踪 `requirements.txt`）。

## 发布与签名

正式发布的 `index.exe` 应带 Authenticode 签名，并在 Release 里附上 SHA256。
校验签名：

```powershell
Get-AuthenticodeSignature .\index.exe | Format-List
```

签名接入方式见 [docs/signing.md](signing.md)。
