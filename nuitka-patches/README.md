# Nuitka MSIX/APPX 引导层补丁

给 Nuitka 的 onefile Windows 引导层打补丁，修掉**Windows 商店版（APPX / MSIX）照片识别启动即退**的问题。

## 故障现象

商店版里点「开始分析」，引擎一起来就退，日志里没有识别结果、没有 Python traceback：

| 退出码 | 含义 |
|---|---|
| `0xC0000135`（3221225781） | `STATUS_DLL_NOT_FOUND` —— 本次定位到的根因 |
| `0xC0000409`（3221226505） | fail-fast 原生异常，**没有调用栈，尚未归因**，若修复后仍出现请单独取证 |

## 根因

Windows 商店版（MSIX / APPX）带**包文件虚拟化**：打包应用写 `%LOCALAPPDATA%` 下的路径时，实际落在包私有目录。

```
逻辑路径 A = %LOCALAPPDATA%\MeteorMasterDetector\<BUILD_TAG>
物理路径 B = %LOCALAPPDATA%\Packages\<PFN>\LocalCache\Local\MeteorMasterDetector\<BUILD_TAG>
```

onefile 引导层把载荷解压到 A（物理上落在 B），随后用**逻辑路径**启动内部子进程：

```c
// OnefileBootstrap.c（Nuitka 2.7.13）
filename_char_t const *fork_binary = first_filename;   // ← 逻辑路径 A
...
bool_res = CreateProcessW(fork_binary, ...);            // ← lpApplicationName = A
```

Windows 加载器打开 `A\index.exe` 时被虚拟化重定向到 `B\index.exe`（**镜像加载成功**），但它把**请求时用的逻辑路径 A** 当成「应用目录」去查依赖 DLL：

```
Load Image  B\...\index.exe              ✅ 成功
QueryOpen   A\...\python312.dll          ❌ PATH NOT FOUND
```

> 上面两段 C 代码引自 Nuitka 2.7.13 的 `OnefileBootstrap.c`
> （Copyright 2025 Kay Hayen and others，Apache-2.0），仅用于说明补丁锚点位置。

`python312.dll` 只存在于 B —— 于是子进程在 **Python 解释器加载之前**就以 `0xC0000135` 退出。

这也解释了为什么「手动在外部跑一次就好了」：外部运行会在普通 AppData 的 A 里真的生成一份完整文件（含 `python312.dll`），之后原启动链去 A 查就能命中 —— 那是**绕过**，不是修复。

## 修法

启动内部子进程前，把逻辑路径解析成最终物理路径，用物理路径作为 `CreateProcessW` 的 `lpApplicationName`：

```
CreateFileW(逻辑路径, 0, FILE_SHARE_READ|WRITE|DELETE, OPEN_EXISTING)   // 仅查询属性
  → GetFinalPathNameByHandleW(FILE_NAME_NORMALIZED | VOLUME_NAME_DOS)
  → 去掉 \\?\ / \\?\UNC\ 前缀
  → CreateProcessW(物理路径, ...)
```

这样子进程的「应用目录」指向真实目录 B，`python312.dll` 就在旁边。

### 为什么不用别的做法

| 做法 | 为什么不行 |
|---|---|
| 在 `index.py` 里加 DLL 目录 / 设 `PATH` / try-catch | 解释器根本没加载起来，Python 代码执行不到 |
| 只建缓存目录 / 换模型 / 装系统 Python | 消不掉 A 与 B 的搜索路径差异；引擎本就应自带解释器 |
| 在 MMA 里硬编码物理路径绕过 onefile | 丢掉首次解压、缓存校验与版本隔离，升级后可能执行旧缓存 |
| 只对外层 exe 做 realpath | 外层本来就能启动，问题出在内部子进程的路径选择 |

## 用法

`build.py` 在调用 Nuitka 之前会自动执行本补丁，无需手动操作：

```bash
call "D:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
python build.py
```

也可以单独执行（幂等）：

```bash
python nuitka-patches\patch_onefile_bootstrap.py
```

## 补丁的自我保护

补丁脚本刻意做得很「死」，避免换机器构建时**静默漏打**：

1. **锁版本**：只接受 Nuitka `2.7.13`。版本不符直接失败（不猜）。
2. **锁内容**：三处锚点（`getCommandLineForChildProcess`、`fork_binary` 选取、`CreateProcessW` 调用）必须**各命中且仅命中一次**，否则直接失败。
3. **锁编码**：**注入的 C 代码必须是纯 ASCII**，且打完补丁后会再扫一遍全文件 —— 任何一行以 DBCS 前导字节（0x81–0xFE）结尾就直接失败。
4. **幂等 + 确定性重放**：始终以 `.mma-orig` 备份为真源重新打补丁，重复执行结果一致（上一轮打了半截补丁也会被覆盖掉）。
5. **可回滚**：首次修改前在原地留一份 `OnefileBootstrap.c.mma-orig`，把备份复制回去即可还原。

补丁本体在**仓库里**（本目录），不手改本机 `site-packages` —— `site-packages` 里的改动只是每次构建的副产物。

### ★ 为什么 C 代码必须纯 ASCII（踩过的坑）

MSVC 默认按**系统代码页**解读源文件（本机是 936 / GBK）。UTF-8 编码的中文注释，其**尾字节会落在 DBCS 前导字节区间（0x81–0xFE）**。如果某个中文注释行恰好以这样的字节结尾，MSVC 的 DBCS 解码器会把「前导字节 + 换行」当成一个**非法双字节字符**——**换行被吞掉**，下一行的 `#endif` 就被 `//` 注释吃掉，编译直接报：

```
static_src\OnefileBootstrap.c(1362): fatal error C1020: unterminated #endif
```

报错行号指向那条中文注释，**不是**真正出错的 `#endif`，非常容易误判成「补丁写错了」。Nuitka 自己的源码是纯 ASCII，补丁也应该保持一致 —— 注释一律用英文。

> 排查手法：逐行扫文件，看有没有哪一行的**最后一个字节**落在 0x81–0xFE。原版 Nuitka 源码是 0 行，插了中文注释后立刻变成 13 行 —— 数量对得上就是它。


## 兼容性注意

* 只在 Windows 生效；解析失败时**回退到原逻辑路径**，非商店环境行为完全不变。
* 不改 `NUITKA_ONEFILE_DIRECTORY` / `NUITKA_ORIGINAL_ARGV0` 的语义 —— Nuitka 用它们定位外部资源，不能无脑替换成缓存目录。
* 子进程的 `argv[0]` 仍由 `getCommandLineForChildProcess()` 设为外层 exe 路径，未被改动。
* 诊断信息写 **stderr**（`[Nuitka onefile] fork target: logical="..." final="..."`），**stdout 是识别结果的 JSON 行协议，不能污染**。

## 验收要点

补丁只是「必要条件」，是否彻底解决必须由 **APPX 无缓存首启** 验收：

- 新账号 / 隔离测试机 + 新 `BUILD_TAG`，普通缓存与包私有缓存**都不存在**
- 直接在软件里首次识别成功，**不预跑、不提权、不手工补 DLL**
- PML 里能看到 `python312.dll` 的有效 Load Image，且实际路径与期望缓存一致
- 回归：监听模式、主动停止、模型切换、CPU / DirectML、中文与空格路径、升级与旧缓存共存

## 参考

* [MSIX 包文件系统虚拟化](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes)
* [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
* [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)
* [DLL 搜索顺序](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order)
* [Nuitka 2.7.13 OnefileBootstrap.c](https://github.com/Nuitka/Nuitka/blob/2.7.13/nuitka/build/static_src/OnefileBootstrap.c)
