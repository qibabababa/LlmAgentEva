#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bug代码执行和验证模块
用于验证修复后的代码是否通过测试用例
"""

import sys
from pathlib import Path
from typing import List

# 使用公共工具模块
from lib.core.utils import dynamic_import

# ------------ ground truth ------------
GROUND_TRUTH = [1, 2, 3, 4, 5]      # 与测试集 test_1.txt 中 5 组数据一一对应
# --------------------------------------


def validate(module_path: str, test_file: str, gt_list):
    # 1. 导入待测代码
    try:
        mod = dynamic_import(module_path)
    except Exception as e:
        print(f"[ERROR] 导入 {module_path} 失败: {e}")
        return False

    # 2. 确认接口存在
    if not hasattr(mod, "process_test_cases"):
        print(f"[ERROR] {module_path} 中未找到函数 process_test_cases")
        return False

    # 3. 调用接口得到结果
    try:
        results = mod.process_test_cases(test_file)
    except Exception as e:
        print(f"[ERROR] 执行 process_test_cases 失败: {e}")
        return False

    # 4. 长度检查
    if len(results) != len(gt_list):
        print(f"[WARN] 结果数量({len(results)})与 ground truth({len(gt_list)}) 不一致")

    # 5. 逐一比对
    print("---------- 验证结果 ----------")
    all_pass = True
    for idx, (pred, gt) in enumerate(zip(results, gt_list), 1):
        status = "PASS" if pred == gt else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"Test case {idx}: 预测={pred:<5}  GT={gt:<5}  -> {status}")

    # 如测试集或 ground-truth 长度不一致, 补充打印
    if len(results) < len(gt_list):
        for idx in range(len(results)+1, len(gt_list)+1):
            print(f"Test case {idx}: 预测=<缺失>  GT={gt_list[idx-1]}  -> FAIL")
            all_pass = False
    elif len(results) > len(gt_list):
        for idx in range(len(gt_list)+1, len(results)+1):
            print(f"Test case {idx}: 预测={results[idx-1]}  GT=<缺失>  -> FAIL")
            all_pass = False

    return all_pass


def main():
    if len(sys.argv) != 3:
        print("Usage: python verify.py fix_bug.py test_1.txt")
        sys.exit(1)

    module_path = sys.argv[1]
    test_file   = sys.argv[2]
    validate(module_path, test_file, GROUND_TRUTH)


if __name__ == "__main__":
    main()
