"""
macOS 打包脚本 (Nuitka standalone / 多文件分发)

用法:
    conda activate MMAD-package
    python build_mac.py

产物:
    dist/index.dist/index.bin    (可执行文件)
    dist/index.dist/             (依赖库目录, 需整体拷贝)

重要:
    可执行文件名必须是 index.bin —— MMA 端 utils-main/baseEngine.js 里写死
    MeteorMasterDetecterAI: { entry: './index.bin' } (Windows 为 index.exe)。
    改名会导致 MMA spawn ENOENT, 表现为"监控启动失败", 退出码 -2。

说明:
    - 仅使用 Nuitka, 不使用 PyInstaller
    - 去掉 Windows 专用参数 (--mingw64)
    - index.py 仅依赖 onnxruntime / numpy / cv2 / PIL / watchdog,
      因此显式排除 torch / scipy / ultralytics 等重型无关依赖
"""

import os
import subprocess
import sys

APP_NAME = "index.bin"
ENTRY = "index.py"
OUTPUT_DIR = "dist"

# index.py 实际用到的运行时包
INCLUDE_PACKAGES = [
    "onnxruntime",
    "cv2",
    "numpy",
    "PIL",
    "watchdog",
]

# 明确排除的重型/无关依赖, 显著减小体积并缩短编译时间
EXCLUDE_IMPORTS = [
    "torch",
    "torchvision",
    "scipy",
    "ultralytics",
    "matplotlib",
    "pandas",
    "polars",
    "tkinter",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "IPython",
    "jupyter",
    "notebook",
    "setuptools",
    "pip",
    "pytest",
    "unittest",
    "pydoc_data",
    "lib2to3",
    "distutils",
    "sqlite3",
    "xmlrpc",
    "curses",
    "test",
    "unittest",
]


def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))

    command = [
        "nuitka",
        # 分发模式: 生成含依赖目录的多文件包
        "--standalone",
        # 目标机器架构
        f"--macos-target-arch={os.uname().machine}",
        # 输出
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",
        f"--remove-output",
        # 编译选项
        "--lto=no",
        "--show-progress",
        "--show-scons",
        # 包含运行时包
        "--include-package=onnxruntime",
        "--include-package=watchdog",
        "--include-package-data=onnxruntime",
        "--include-package-data=cv2",
        # 显式模块包含 (绕开 Nuitka 静态分析盲区)
        "--include-module=onnxruntime.capi._pybind_state",
        "--include-module=watchdog.observers",
        "--include-module=watchdog.events",
        "--include-module=cv2",
        "--include-module=PIL.Image",
        # 排除无关依赖
    ]

    for module in EXCLUDE_IMPORTS:
        command.append(f"--nofollow-import-to={module}")

    command.append(ENTRY)

    print("[build_mac] 执行命令:")
    print(" ".join(command))
    print("-" * 70)

    result = subprocess.run(command, cwd=project_dir)

    # 注意: Nuitka 以入口脚本名 (index.py) 命名分发目录, 而非 --output-filename
    entry_name = os.path.splitext(ENTRY)[0]
    dist_dir = os.path.join(project_dir, OUTPUT_DIR, f"{entry_name}.dist")
    binary = os.path.join(dist_dir, APP_NAME)

    print("-" * 70)
    if result.returncode == 0 and os.path.exists(binary):
        print(f"[build_mac] 打包成功: {binary}")
        print(f"[build_mac] 请整体拷贝目录: {dist_dir}")
    else:
        print(f"[build_mac] 打包失败 (returncode={result.returncode})", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(build())
