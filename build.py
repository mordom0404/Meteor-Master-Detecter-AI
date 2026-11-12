"""Nuitka 打包脚本 —— Windows 单文件 (onefile)。

readme.md「打包成单文件 (win)」一节给的是简化版，这里是完整版，补上了
readme 里提到但没展开的那批参数：
  - --nofollow-import-to=  排除 requirements.txt 里"挂名"但不实际 import 的包
  - --noinclude-data-files= 排除 PIL 的字体文件（显著减小体积）
  - --include-data-files=   把 cv2/config*.py 显式带进 bundle

★ 打包前会先跑 nuitka-patches/patch_onefile_bootstrap.py：
  给 Nuitka 的 onefile Windows 引导层打 MSIX/APPX 包虚拟化补丁。
  商店版(APPX)下逻辑缓存路径会被重定向到包私有目录，内部子进程若用逻辑路径
  启动，Windows 加载器找不到同目录的 python312.dll，子进程以 0xC0000135 退出。
  详见 nuitka-patches/README.md。补丁命中不上会直接失败，不会静默漏打。

编译器：readme 推荐 MSVC（VS 2022 BuildTools 自带 cl.exe）。本脚本走 MSVC，
不要加 --mingw64（那是旧版本的写法）。

用法：
    # 用当前 Python 打包（推荐：先激活/安装好依赖的环境再运行）
    python build.py

    # 显式指定打包环境的 Python 解释器（CI 或本机多环境时用）
    set MMAD_BUILD_PYTHON=C:\\path\\to\\python.exe
    python build.py

环境变量：
    MMAD_BUILD_PYTHON  打包用的 Python 解释器，默认 sys.executable
    MMAD_BUILD_TAG     onefile 解压缓存标识，默认 "<index.py VERSION>-build1"
                       （发布新构建/依赖变化时 bump，避免复用旧缓存）
"""

import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_SCRIPT = os.path.join(HERE, "nuitka-patches", "patch_onefile_bootstrap.py")
INDEX_PY = os.path.join(HERE, "index.py")

# 打包环境（onnxruntime-directml + opencv-python + pillow + watchdog）。
# 默认用"当前正在运行 build.py 的 Python"，避免把某台机器的绝对路径写死。
PYENV = os.environ.get("MMAD_BUILD_PYTHON") or sys.executable


def read_version(path=INDEX_PY):
    """从 index.py 读取 VERSION，保证 exe 版本号和源码一致。"""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                match = re.match(r"""^VERSION\s*=\s*["']([^"']+)["']""", line)
                if match:
                    return match.group(1)
    except OSError:
        pass
    return "0.0.0"


VERSION = read_version()


def numeric_version(version=VERSION):
    """把 "2.5.0" 这类版本号转成 Windows 资源要求的 4 段数字 "2.5.0.0"。"""
    parts = re.findall(r"\d+", version)[:4] or ["0"]
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts)


# 发布新构建（包括依赖变化）时，改 MMAD_BUILD_TAG 或 bump index.py 的 VERSION，
# 避免不同构建共用 onefile 解压缓存。
BUILD_TAG = os.environ.get("MMAD_BUILD_TAG") or "%s-build1" % VERSION


def apply_nuitka_patch(python=PYENV):
    """给 Nuitka 引导层打 MSIX/APPX 补丁。

    补丁本体在仓库里（nuitka-patches/），不手改 site-packages。
    脚本内部会校验 Nuitka 版本与被改文件的预期内容，命中不上直接失败。
    """
    if not os.path.isfile(PATCH_SCRIPT):
        sys.exit("找不到补丁脚本：%s" % PATCH_SCRIPT)

    print("=" * 70)
    print("应用 Nuitka MSIX/APPX 引导层补丁")
    print("=" * 70)
    result = subprocess.run([python, PATCH_SCRIPT])
    if result.returncode != 0:
        sys.exit("Nuitka 补丁失败（退出码 %d），已中止构建。" % result.returncode)
    print()


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_build_report(output_dir, exe, python=PYENV):
    """记录构建报告：源码提交、Nuitka/Python 版本、依赖版本、最终产物哈希。"""
    report_path = os.path.join(HERE, "build_report.txt")
    lines = []

    def run(args):
        try:
            return subprocess.run(args, capture_output=True, text=True).stdout.strip()
        except Exception as error:
            return "N/A (%s)" % error

    try:
        commit = run(["git", "-C", HERE, "rev-parse", "HEAD"])
        dirty = run(["git", "-C", HERE, "status", "--porcelain"])
    except Exception:
        commit, dirty = "N/A", "N/A"

    lines.append("MeteorMasterDetecterAI 构建报告")
    lines.append("=" * 60)
    lines.append("版本               : %s" % VERSION)
    lines.append("BUILD_TAG          : %s" % BUILD_TAG)
    lines.append("源码提交           : %s" % commit)
    lines.append("工作区有未提交改动 : %s" % ("是" if dirty else "否"))
    lines.append("Python             : %s" % run([python, "--version"]))
    nuitka_version_lines = run([python, "-m", "nuitka", "--version"]).splitlines()
    lines.append("Nuitka             : %s" % (nuitka_version_lines[0] if nuitka_version_lines else "N/A"))
    lines.append("Nuitka 补丁        : nuitka-patches/patch_onefile_bootstrap.py（MSIX/APPX 物理路径修复）")
    lines.append("编译器             : MSVC (VS 2022 BuildTools cl.exe)")
    lines.append("签名状态           : 未签名（分发前另行签名，签名后哈希需重新记录）")
    lines.append("")
    lines.append("依赖版本：")
    for line in run([python, "-m", "pip", "freeze"]).splitlines():
        if any(key in line.lower() for key in ("nuitka", "onnxruntime", "opencv", "pillow", "watchdog", "numpy")):
            lines.append("  %s" % line)
    lines.append("")
    if os.path.isfile(exe):
        lines.append("最终分发 EXE       : %s" % exe)
        lines.append("大小               : %d 字节" % os.path.getsize(exe))
        lines.append("SHA256             : %s" % sha256_of(exe))
        lines.append("")
        lines.append("分发缓存目录       : <user cache>\\MeteorMasterDetector\\%s" % BUILD_TAG)

    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("构建报告已写入：%s" % report_path)


def build(python=PYENV, output_dir="dist"):
    # 先打补丁：没补丁的 onefile 在商店版里起不来。
    apply_nuitka_patch(python)

    sp = subprocess.run(
        [python, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    # cv2 的 config*.py 运行时会被 bootstrap 引用，显式带进 bundle
    cv2cfg = os.path.join(sp, "cv2", "config.py")
    cv2cfg3 = os.path.join(sp, "cv2", "config-3.py")

    # 构建报告目录（Nuitka XML 报告与 pip freeze 证据，不进仓库）
    report_dir = os.path.join(HERE, "build")
    os.makedirs(report_dir, exist_ok=True)

    command = [
        python, "-m", "nuitka",
        "--standalone",   # 包含独立运行所需的依赖
        "--onefile",      # 单文件打包，首次运行解压到固定缓存目录
        "--onefile-tempdir-spec={CACHE_DIR}/MeteorMasterDetector/%s" % BUILD_TAG,
        "--lto=no",
        "--show-progress",
        "--assume-yes-for-downloads",
        # Windows 版本资源：SignPath 等签名渠道要求被签二进制必须带
        # product name / version 元数据，并且能在签名策略里强制校验。
        "--windows-company-name=MeteorMasterDetecterAI",
        "--windows-product-name=MeteorMasterDetecterAI",
        "--windows-file-description=MeteorMasterDetecterAI ONNX inference engine",
        "--windows-file-version=%s" % numeric_version(),
        "--windows-product-version=%s" % numeric_version(),
        # 构建报告：记录实际打进 bundle 的模块，便于核对第三方许可清单
        "--report=%s" % os.path.join(report_dir, "nuitka-report.xml"),
        # 排除 requirements.txt 里挂名但 index.py 实际不 import 的重型包
        "--nofollow-import-to=torch",
        "--nofollow-import-to=torchvision",
        "--nofollow-import-to=ultralytics",
        "--nofollow-import-to=scipy",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=sympy",
        "--nofollow-import-to=polars",
        "--nofollow-import-to=tk-inter",
        # PIL 的字体文件用不到（识别流程不画文字），排掉省体积
        "--noinclude-data-files=*.ttf",
        "--noinclude-data-files=*.otf",
        "--include-data-files=%s=cv2/config.py" % cv2cfg,
        "--include-data-files=%s=cv2/config-3.py" % cv2cfg3,
        f"--output-dir={output_dir}",
        "index.py",
    ]

    # 把第三方许可清单打进 onefile，离线用户也能用 `index.exe --licenses` 看到
    notices = os.path.join(HERE, "THIRD_PARTY_NOTICES.md")
    if os.path.isfile(notices):
        command.insert(
            command.index("--output-dir=%s" % output_dir),
            "--include-data-files=%s=THIRD_PARTY_NOTICES.md" % notices,
        )

    print("nuitka command:")
    print(" ".join(command))
    result = subprocess.run(command)
    if result.returncode != 0:
        sys.exit(result.returncode)

    exe = os.path.join(output_dir, "index.exe")
    if os.path.isfile(exe):
        mb = os.path.getsize(exe) / 1024 / 1024
        print("\nOK: %s  (%0.1f MB)" % (exe, mb))
        print("解压缓存: <user cache>\\MeteorMasterDetector\\%s" % BUILD_TAG)
        write_build_report(output_dir, exe, python)
    else:
        print("构建结束但没找到 %s，请检查上面的编译日志。" % exe)


if __name__ == "__main__":
    build()
