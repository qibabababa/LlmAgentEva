#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码转换验证模块
用于验证JavaScript代码转换是否正确
"""

import json
import subprocess
from pathlib import Path

# 使用公共工具模块
from lib.core.utils import normalize_output


def validate_js_cases(js_file: str | Path, cases_file: str | Path) -> bool:
    """
    逐条把 cases.json 的输入喂给 js_file（node 运行）。
    对输出做轻度规范化后与 expected 比较。
    全部通过则返回 True。
    """
    try:
        with open(cases_file, "r", encoding="utf-8") as fh:
            cases = json.load(fh)
    except Exception as e:
        print(f"❌ 读取测试用例失败: {e}")
        return False

    for case in cases:
        proc = subprocess.run(
            ["node", str(js_file)],
            input=case["input"],
            text=True,
            capture_output=True
        )

        if proc.returncode != 0:
            print(f"❌ JS 运行错误: {proc.stderr}")
            return False

        expected_norm = normalize_output(case["expected"])
        actual_norm   = normalize_output(proc.stdout)

        if actual_norm != expected_norm:
            print(f"❌ 用例 '{case['name']}' 不通过")
            print(f"   期望: {repr(case['expected'])}")
            print(f"   实际: {repr(proc.stdout)}")
            return False

    print("✅ 所有 JS 用例通过")
    return True
