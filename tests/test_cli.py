"""CLI 冒烟测试：不需要模型权重，也不需要显卡。

覆盖参数解析、模式互斥、错误退出码——这些是 MMA 主程序调用引擎时
最容易被破坏的契约，顺便保证 CI 能跑通"装完依赖就能 import"。

运行：
    python -m unittest discover -s tests -v
"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.py")

FLAGS = (
    "--mask",
    "--img_directory",
    "--img_directory_list",
    "--watch_folder",
    "--onnx_path",
    "--force_CPU",
    "--no_45",
    "--debug",
    "--processed_log",
    "--exclude_log",
)


def run_engine(*args, timeout=180):
    env = dict(os.environ)
    # 输出含中文（--licenses），固定 UTF-8，避免不同 Windows 代码页导致解码差异
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, INDEX, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )


class CliSmokeTest(unittest.TestCase):
    def test_help_lists_all_arguments(self):
        result = run_engine("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in FLAGS:
            self.assertIn(flag, result.stdout)

    def test_version_flag(self):
        result = run_engine("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2.6.1", result.stdout)

    def test_licenses_flag_does_not_require_model(self):
        result = run_engine("--licenses")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Third-Party", result.stdout)

    def test_missing_mode_is_usage_error(self):
        result = run_engine()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--watch_folder", result.stderr)
        self.assertIn("--img_directory", result.stderr)

    def test_watch_folder_and_one_shot_are_mutually_exclusive(self):
        result = run_engine("--watch_folder", "inbox", "--img_directory", "images")
        self.assertEqual(result.returncode, 2)
        self.assertIn("mutually exclusive", result.stderr)

    def test_img_directory_list_must_be_json(self):
        result = run_engine("--img_directory_list", "list.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a .json file", result.stderr)


if __name__ == "__main__":
    unittest.main()
