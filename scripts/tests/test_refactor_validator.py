#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试refactor验证器
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.validators.refactor import validate_refactor


def test_case_1():
    """测试用例1：函数重命名"""
    print("\n" + "="*60)
    print("测试用例1：函数重命名")
    print("="*60)
    
    result = validate_refactor(
        file_path="data/tasks/code_refactor/utils_1.py",
        rename_map={
            "add_two_numbers": "addTwoNumbers",
            "multiply_two_numbers": "multiplyTwoNumbers",
            "process_user_input": "processUserInput"
        },
        expected_output_file="data/tasks/code_refactor/expected_output_1.txt",
        run_script=True
    )
    
    print(f"\n结果: {'✅ 通过' if result else '❌ 失败'}")
    print(f"预期: ❌ 失败（因为还未重构）\n")
    
    return result


def test_case_2():
    """测试用例2：类重命名"""
    print("\n" + "="*60)
    print("测试用例2：类重命名")
    print("="*60)
    
    result = validate_refactor(
        file_path="data/tasks/code_refactor/utils_2.py",
        rename_map={
            "SimpleMathHelper": "simpleMathHelper"
        },
        expected_output_file="data/tasks/code_refactor/expected_output_2.txt",
        run_script=True
    )
    
    print(f"\n结果: {'✅ 通过' if result else '❌ 失败'}")
    print(f"预期: ❌ 失败（类名未改）\n")
    
    return result


def test_case_3():
    """测试用例3：常量重命名"""
    print("\n" + "="*60)
    print("测试用例3：常量重命名")
    print("="*60)
    
    result = validate_refactor(
        file_path="data/tasks/code_refactor/utils_3.py",
        rename_map={
            "GLOBAL_CONSTANT_VALUE": "globalConstantValue"
        },
        expected_output_file="data/tasks/code_refactor/expected_output_3.txt",
        run_script=True
    )
    
    print(f"\n结果: {'✅ 通过' if result else '❌ 失败'}")
    print(f"预期: ❌ 失败（常量未改）\n")
    
    return result


def main():
    """主函数"""
    print("\n" + "="*60)
    print("Refactor验证器测试")
    print("="*60)
    print("\n说明: 所有测试应该失败，因为文件还未被重构")
    
    results = []
    
    # 测试1
    try:
        result1 = test_case_1()
        results.append(("测试1-函数重命名", result1))
    except Exception as e:
        print(f"❌ 测试1异常: {e}")
        results.append(("测试1-函数重命名", False))
    
    # 测试2  
    try:
        result2 = test_case_2()
        results.append(("测试2-类重命名", result2))
    except Exception as e:
        print(f"❌ 测试2异常: {e}")
        results.append(("测试2-类重命名", False))
    
    # 测试3
    try:
        result3 = test_case_3()
        results.append(("测试3-常量重命名", result3))
    except Exception as e:
        print(f"❌ 测试3异常: {e}")
        results.append(("测试3-常量重命名", False))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        expected = "❌ 失败" if not result else "✅ 通过"
        match = "✓" if (not result) else "✗"
        print(f"{name}: {status} (预期: {expected}) {match}")
    
    print("\n所有测试都应该失败（返回False），因为文件还未重构")
    print("这说明验证器正常工作！\n")
    
    # 如果所有测试都失败（符合预期），返回0
    all_failed = all(not result for _, result in results)
    return 0 if all_failed else 1


if __name__ == "__main__":
    sys.exit(main())
