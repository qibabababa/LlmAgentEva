#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试任务分解和任务规划验证器
"""

import sys
from pathlib import Path

# 添加lib目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.validators.task_decomposition import (
    validate_task_decomposition,
    generate_task_decomposition_prompt
)
from lib.validators.task_planning import (
    validate_task_planning,
    generate_task_planning_prompt
)


def test_task_decomposition():
    """测试任务分解验证"""
    print("\n" + "=" * 70)
    print("测试1: 任务分解验证（开放模式）")
    print("=" * 70)
    
    # 标准答案
    ground_truth = [
        "列出指定目录下的所有文件",
        "读取bug_code_1.py文件内容",
        "修复代码并写入到fix_code_1.py文件中",
        "向用户解释bug出现的原因和修复方案"
    ]
    
    # 模型输出（JSON格式）
    model_response_good = """
    {
        "goal": "修复bug_code_1.py中的bug",
        "tasks": [
            "查看目录下所有文件",
            "读取bug_code_1.py文件内容",
            "修复bug并将修复后的代码写入到fix_code_1.py文件中",
            "向用户解释bug出现的原因和修复方案"
        ]
    }
    """
    
    passed, details = validate_task_decomposition(
        model_response=model_response_good,
        ground_truth=ground_truth,
        mode="open",
        format_type="json"
    )
    
    print(f"\n📊 评测结果:")
    print(f"  - 召回率 (Recall): {details['recall']:.2%}")
    print(f"  - 准确率 (Precision): {details['precision']:.2%}")
    print(f"  - F1分数: {details['f1_score']:.2%}")
    print(f"\n📝 匹配详情:")
    print(f"  - 匹配任务数: {details['num_matched']}")
    print(f"  - 标准任务数: {details['num_ground_truth']}")
    print(f"  - 模型输出数: {details['num_model_output']}")
    
    if details.get('matched_pairs'):
        print(f"\n✓ 匹配的任务对:")
        for model_task, gt_task, similarity in details['matched_pairs']:
            print(f"  - '{model_task[:40]}...' <-> '{gt_task[:40]}...' ({similarity})")
    
    if details.get('missed_tasks'):
        print(f"\n✗ 未召回的任务:")
        for task in details['missed_tasks']:
            print(f"  - {task}")
    
    if details.get('extra_tasks'):
        print(f"\n⚠ 多余的任务:")
        for task in details['extra_tasks']:
            print(f"  - {task}")
    
    # 测试全集模式
    print("\n" + "=" * 70)
    print("测试2: 任务分解验证（全集模式）")
    print("=" * 70)
    
    all_tasks = ground_truth + [
        "运行测试用例",
        "检查代码风格",
        "生成文档"
    ]
    
    model_response_constrained = """
    {
        "goal": "修复bug_code_1.py中的bug",
        "tasks": [
            "列出指定目录下的所有文件",
            "读取bug_code_1.py文件内容",
            "修复代码并写入到fix_code_1.py文件中"
        ]
    }
    """
    
    details = validate_task_decomposition(
        model_response=model_response_constrained,
        ground_truth=ground_truth,
        mode="constrained",
        format_type="json"
    )
    
    print(f"\n📊 评测结果:")
    print(f"  - 召回率 (Recall): {details['recall']:.2%}")
    print(f"  - 准确率 (Precision): {details['precision']:.2%}")
    print(f"  - F1分数: {details['f1_score']:.2%}")


def test_task_planning():
    """测试任务规划验证"""
    print("\n" + "=" * 70)
    print("测试3: 任务规划验证")
    print("=" * 70)
    
    # 任务列表
    tasks = [
        "列出指定目录下的所有文件",
        "读取bug_code_1.py文件内容",
        "修复代码并写入到fix_code_1.py文件中",
        "向用户解释bug出现的原因和修复方案"
    ]
    
    # 依赖关系
    dependencies = {
        "读取bug_code_1.py文件内容": ["列出指定目录下的所有文件"],
        "修复代码并写入到fix_code_1.py文件中": ["读取bug_code_1.py文件内容"],
        "向用户解释bug出现的原因和修复方案": ["修复代码并写入到fix_code_1.py文件中"]
    }
    
    # 标准答案规划
    ground_truth_planning = [
        ["列出指定目录下的所有文件"],
        ["读取bug_code_1.py文件内容"],
        ["修复代码并写入到fix_code_1.py文件中"],
        ["向用户解释bug出现的原因和修复方案"]
    ]
    
    # 模型输出（正确顺序）
    model_response_good = """
    [
        ["列出指定目录下的所有文件"],
        ["读取bug_code_1.py文件内容"],
        ["修复代码并写入到fix_code_1.py文件中"],
        ["向用户解释bug出现的原因和修复方案"]
    ]
    """
    
    details = validate_task_planning(
        model_response=model_response_good,
        ground_truth_tasks=tasks,
        dependencies=dependencies,
        ground_truth_planning=ground_truth_planning
    )
    
    print(f"\n📊 评测结果:")
    print(f"  - 集合覆盖度 (Coverage): {details['coverage']:.2%}")
    print(f"  - 顺序正确性 (Order): {details['order_correctness']:.2%}")
    print(f"  - 层级效率 (Efficiency): {details['level_efficiency']:.2%}")
    print(f"  - 综合得分 (Overall): {details['overall_score']:.2%}")
    
    print(f"\n📝 规划详情:")
    print(f"  - 层级数: {details['num_levels']}")
    print(f"  - 匹配任务数: {details['num_matched']}/{details['num_ground_truth']}")
    
    if details.get('model_planning'):
        print(f"\n📋 模型的规划:")
        for i, level in enumerate(details['model_planning'], 1):
            print(f"  层级 {i}: {level}")
    
    if details.get('dependency_violations'):
        print(f"\n⚠ 依赖违反:")
        for violation in details['dependency_violations']:
            print(f"  - {violation['description']}")
    
    # 测试错误顺序
    print("\n" + "=" * 70)
    print("测试4: 任务规划验证（错误顺序）")
    print("=" * 70)
    
    model_response_bad = """
    [
        ["修复代码并写入到fix_code_1.py文件中"],
        ["读取bug_code_1.py文件内容"],
        ["列出指定目录下的所有文件"],
        ["向用户解释bug出现的原因和修复方案"]
    ]
    """
    
    details = validate_task_planning(
        model_response=model_response_bad,
        ground_truth_tasks=tasks,
        dependencies=dependencies,
        ground_truth_planning=ground_truth_planning
    )
    
    print(f"\n📊 评测结果:")
    print(f"  - 集合覆盖度 (Coverage): {details['coverage']:.2%}")
    print(f"  - 顺序正确性 (Order): {details['order_correctness']:.2%}")
    print(f"  - 层级效率 (Efficiency): {details['level_efficiency']:.2%}")
    print(f"  - 综合得分 (Overall): {details['overall_score']:.2%}")
    
    if details.get('dependency_violations'):
        print(f"\n⚠ 依赖违反 ({len(details['dependency_violations'])} 个):")
        for violation in details['dependency_violations']:
            print(f"  - {violation['description']}")


def test_prompt_generation():
    """测试prompt生成"""
    print("\n" + "=" * 70)
    print("测试5: Prompt生成")
    print("=" * 70)
    
    question = "目录下存在一个名为bug_code_1.py的文件，这个文件存在bug,帮我修复这个bug,并修复代码并写入到fix_code_1.py文件中。"
    
    # 开放模式
    print("\n🔓 开放模式Prompt:")
    print("-" * 70)
    prompt = generate_task_decomposition_prompt(
        question=question,
        mode="open",
        format_type="json"
    )
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    
    # 全集模式
    print("\n🔒 全集模式Prompt:")
    print("-" * 70)
    all_tasks = [
        "列出指定目录下的所有文件",
        "读取bug_code_1.py文件内容",
        "修复代码并写入到fix_code_1.py文件中",
        "向用户解释bug出现的原因和修复方案",
        "运行测试用例",
        "检查代码风格"
    ]
    prompt = generate_task_decomposition_prompt(
        question=question,
        mode="constrained",
        all_tasks=all_tasks,
        format_type="json"
    )
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
    
    # 任务规划
    print("\n📋 任务规划Prompt:")
    print("-" * 70)
    tasks = [
        "列出指定目录下的所有文件",
        "读取bug_code_1.py文件内容",
        "修复代码并写入到fix_code_1.py文件中",
        "向用户解释bug出现的原因和修复方案"
    ]
    dependencies = {
        "读取bug_code_1.py文件内容": ["列出指定目录下的所有文件"],
        "修复代码并写入到fix_code_1.py文件中": ["读取bug_code_1.py文件内容"],
        "向用户解释bug出现的原因和修复方案": ["修复代码并写入到fix_code_1.py文件中"]
    }
    prompt = generate_task_planning_prompt(
        tasks=tasks,
        dependencies=dependencies
    )
    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("🧪 任务分解和任务规划验证器测试")
    print("=" * 70)
    
    try:
        test_task_decomposition()
        test_task_planning()
        test_prompt_generation()
        
        print("\n" + "=" * 70)
        print("✅ 所有测试完成！")
        print("=" * 70)
        
        print("\n📚 使用说明:")
        print("  1. 任务分解验证器: lib/validators/task_decomposition.py")
        print("     - validate_task_decomposition(): 验证单个案例")
        print("     - validate_task_decomposition_batch(): 批量验证")
        print("     - 评估指标: Recall, Precision, F1-score")
        
        print("\n  2. 任务规划验证器: lib/validators/task_planning.py")
        print("     - validate_task_planning(): 验证单个案例")
        print("     - validate_task_planning_batch(): 批量验证")
        print("     - 评估指标: Coverage, Order, Efficiency, Overall")
        
        print("\n  3. 评估方式:")
        print("     客观反映各项指标数值，不设置通过标准")
        print("     用户可根据实际需求自行判断评估结果")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
