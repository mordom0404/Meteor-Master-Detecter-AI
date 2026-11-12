"""Nuitka 打包脚本 —— Windows onefile（单文件）或 onedir（目录）两种形态。

onedir 是默认的发布形态：产物是 ``dist/index.dist/`` 整个目录（``index.exe`` +
依赖 DLL），便于直接把目录集成进宿主程序，也便于只对 ``index.exe`` 做代码签名。

用法：
    # onedir（推荐，签名/集成用；产物 dist/index.dist/）
    python build.py --mode onedir

    # onedir + 自动打 zip（产物 dist/MeteorMasterDetecterAI-<版本>-win-onedir.zip）
    python build.py --mode onedir --zip

    # onefile（单文件，旧版分发形态；产物 dist/index.exe）
    python build.py --mode onefile

    # 显式指定打包环境的 Python 解释器（CI 或本机多环境时用）
    set MMAD_BUILD_PYTHON=C:\\path\\to\\python.exe
    python build.py --mode onedir

环境变量：
    MMAD_BUILD_PYTHON  打包用的 Python 解释器，默认 sys.executable
    MMAD_BUILD_MODE    onefile / onedir，默认 onedir（CLI --mode 优先）
    MMAD_BUILD_TAG     onefile 解压缓存标识，默认 "<index.py VERSION>-build1"
                       （发布新构建/依赖变化时 bump，避免复用旧缓存）

说明：
  - 两种模式都会写入 Windows 版本资源（product name / version / file version），
    这是代码签名（SignPath / signtool）的前置要求。
  - onefile 模式会在打包前自动执行 ``nuitka-patches/patch_onefile_bootstrap.py``
    （MSIX/APPX 引导层物理路径修复）；onedir 不经过 onefile 引导层，无需该补丁。
  - 编译器：MSVC（VS 2022 BuildTools 自带 cl.exe），不要加 ``--mingw64``。
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_SCRIPT = os.path.join(HERE, "nuitka-patches", "patch_onefile_bootstrap.py")
INDEX_PY = os.path.join(HERE, "index.py")
APP_NAME = "MeteorMasterDetecterAI"

# 打包环境（onnxruntime-directml + opencv-python + pillow + watchdog）。
# 默认用"当前正在运行 build.py 的 Python"，避免把某台机器的绝对路径写死。
PYENV = os.environ.get("MMAD_BUILD_PYTHON") or sys.executable

MODES = ("onefile", "onedir")


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
    """把 "2.6.0" 这类版本号转成 Windows 资源要求的 4 段数字 "2.6.0.0"。"""
    parts = re.findall(r"\d+", version)[:4] or ["0"]
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts)


# onefile 解压缓存标识（onedir 不使用）。
BUILD_TAG = os.environ.get("MMAD_BUILD_TAG") or "%s-build1" % VERSION

# onedir 产物目录 / zip 名（宿主程序集成时直接拷贝 index.dist/）
ONEDIR_NAME = "index.dist"
ONEDIR_ZIP = "%s-%s-win-onedir.zip" % (APP_NAME, VERSION)


def apply_nuitka_patch(python=PYENV):
    """给 Nuitka onefile 引导层打 MSIX/APPX 补丁（仅 onefile 需要）。"""
    if not os.path.isfile(PATCH_SCRIPT):
        sys.exit("找不到补丁脚本：%s" % PATCH_SCRIPT)

    print("=" * 70)
    print("应用 Nuitka MSIX/APPX 引导层补丁（onefile）")
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


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def write_sha256(path, exe=None):
    """写 `<file>.sha256`（sha256sum 兼容格式），可选同时记录 exe 哈希。"""
    lines = []
    if exe is not None:
        lines.append("%s  %s" % (sha256_of(exe), os.path.basename(exe)))
    lines.append("%s  %s" % (sha256_of(path), os.path.basename(path)))
    with open(path + ".sha256", "w", encoding="ascii", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def write_build_report(output_dir, mode, exe, python=PYENV, extra=()):
    """记录构建报告：源码提交、Nuitka/Python 版本、依赖版本、产物哈希。"""
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

    lines.append("%s 构建报告" % APP_NAME)
    lines.append("=" * 60)
    lines.append("版本               : %s" % VERSION)
    lines.append("打包形态           : %s" % mode)
    if mode == "onefile":
        lines.append("BUILD_TAG          : %s" % BUILD_TAG)
    else:
        lines.append("产物目录           : %s" % ONEDIR_NAME)
    lines.append("源码提交           : %s" % commit)
    lines.append("工作区有未提交改动 : %s" % ("是" if dirty else "否"))
    lines.append("Python             : %s" % run([python, "--version"]))
    nuitka_version_lines = run([python, "-m", "nuitka", "--version"]).splitlines()
    lines.append("Nuitka             : %s" % (nuitka_version_lines[0] if nuitka_version_lines else "N/A"))
    lines.append("Nuitka 补丁        : %s" % (
        "已应用（onefile MSIX/APPX 修复）" if mode == "onefile" else "不适用（onedir 无 onefile 引导层）"
    ))
    lines.append("编译器             : MSVC (VS 2022 BuildTools cl.exe)")
    lines.append("签名状态           : 未签名（分发前另行签名 index.exe，签名后哈希会变化）")
    lines.append("")
    lines.append("依赖版本：")
    for line in run([python, "-m", "pip", "freeze"]).splitlines():
        if any(key in line.lower() for key in ("nuitka", "onnxruntime", "opencv", "pillow", "watchdog", "numpy")):
            lines.append("  %s" % line)
    lines.append("")
    if os.path.isfile(exe):
        lines.append("可执行文件         : %s" % os.path.relpath(exe, HERE))
        lines.append("大小               : %d 字节" % os.path.getsize(exe))
        lines.append("SHA256             : %s" % sha256_of(exe))
        if mode == "onedir":
            lines.append("目录总大小         : %d 字节" % dir_size(os.path.dirname(exe)))
        lines.append("")
        lines.append("分发缓存目录       : %s" % (
            "<user cache>\\MeteorMasterDetector\\%s" % BUILD_TAG
            if mode == "onefile" else "不适用（onedir 直接运行目录内文件）"
        ))
    if extra:
        lines.append("")
        lines.extend(extra)

    with open(report_path, "w", encoding="utf-8-sig") as handle:
        handle.write("\n".join(lines) + "\n")
    print("构建报告已写入：%s" % report_path)


def build(python=PYENV, output_dir="dist", mode="onedir", make_zip=False):
    if mode not in MODES:
        sys.exit("未知打包形态：%s（可选：%s）" % (mode, ", ".join(MODES)))

    if mode == "onefile":
        # 没打补丁的 onefile 在商店版里起不来。
        apply_nuitka_patch(python)
    else:
        print("onedir 模式：跳过 Nuitka onefile 引导层补丁。")

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

    # onedir 产物目录：先清空，避免上一次构建残留文件混进本次产物
    target_dir = os.path.join(output_dir, ONEDIR_NAME)
    if mode == "onedir" and os.path.isdir(target_dir):
        shutil.rmtree(target_dir)

    command = [
        python, "-m", "nuitka",
        "--standalone",   # 包含独立运行所需的依赖（onedir 正是该产物）
        "--lto=no",
        "--show-progress",
        "--assume-yes-for-downloads",
        # Windows 版本资源：签名渠道（SignPath / signtool）要求被签二进制带
        # product name / version 元数据，并能在签名策略里强制校验。
        "--windows-company-name=%s" % APP_NAME,
        "--windows-product-name=%s" % APP_NAME,
        "--windows-file-description=%s ONNX inference engine" % APP_NAME,
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
    ]
    if mode == "onefile":
        command[3:3] = [
            "--onefile",  # 单文件打包，首次运行解压到固定缓存目录
            "--onefile-tempdir-spec={CACHE_DIR}/MeteorMasterDetector/%s" % BUILD_TAG,
        ]
    command += ["--output-dir=%s" % output_dir, "index.py"]

    # 把第三方许可清单打进产物，离线用户也能用 `index.exe --licenses` 看到
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

    if mode == "onefile":
        exe = os.path.join(output_dir, "index.exe")
    else:
        exe = os.path.join(output_dir, ONEDIR_NAME, "index.exe")

    if not os.path.isfile(exe):
        print("构建结束但没找到 %s，请检查上面的编译日志。" % exe)
        return

    mb = os.path.getsize(exe) / 1024 / 1024
    print("\nOK: %s  (%0.1f MB)" % (exe, mb))
    if mode == "onefile":
        print("解压缓存: <user cache>\\MeteorMasterDetector\\%s" % BUILD_TAG)
    else:
        print("目录产物: %s（分发时整个目录一起拷贝）" % os.path.dirname(exe))

    # 产物哈希清单（签名前后各记录一次；签名会改变 exe 哈希）
    write_sha256(exe)
    print("SHA256 : %s" % sha256_of(exe))

    extra = []
    if mode == "onedir" and make_zip:
        zip_path = os.path.join(output_dir, ONEDIR_ZIP)
        if os.path.isfile(zip_path):
            os.remove(zip_path)
        shutil.make_archive(
            os.path.splitext(zip_path)[0], "zip",
            root_dir=output_dir, base_dir=ONEDIR_NAME,
        )
        write_sha256(zip_path, exe=exe)
        print("ZIP    : %s  (%.1f MB)" % (zip_path, os.path.getsize(zip_path) / 1024 / 1024))
        extra.append("ZIP 产物           : %s" % os.path.relpath(zip_path, HERE))
        extra.append("ZIP SHA256         : %s" % sha256_of(zip_path))

    write_build_report(output_dir, mode, exe, python, extra=extra)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MeteorMasterDetecterAI Nuitka 打包脚本")
    parser.add_argument("--mode", choices=MODES,
                        default=os.environ.get("MMAD_BUILD_MODE", "onedir"),
                        help="打包形态：onedir（默认，目录）或 onefile（单文件）")
    parser.add_argument("--output-dir", default="dist", help="输出目录（默认 dist）")
    parser.add_argument("--zip", action="store_true",
                        help="onedir 模式额外打 zip（便于签名/分发）")
    args = parser.parse_args(argv)
    build(output_dir=args.output_dir, mode=args.mode, make_zip=args.zip)


if __name__ == "__main__":
    main()
