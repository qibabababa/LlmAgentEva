#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试简洁的统计输出格式
"""

def test_output_format():
    """模拟评测完成后的输出"""
    
    # 模拟统计数据
    stats = {
        'total': 6,
        'passed': 2,
        'failed': 4,
        'pass_rate': 0.3333333333333333,
        'tool_stats': {
            'total_calls': 25,
            'tool_types': {
                'list_files': 6,
                'read_file': 11,
                'write_to_file': 4,
                'execute_command': 3,
                'replace_in_file': 1
            },
            'avg_calls_per_task': 4.166666666666667
        },
        'round_stats': {
            'total_rounds': 30,
            'avg_rounds': 5.0,
            'max_rounds': 9,
            'min_rounds': 3
        },
        'by_task_type': {
            'fix_bug': {
                'total': 1,
                'passed': 1,
                'failed': 0,
                'pass_rate': 1.0,
                'avg_rounds': 4.0
            },
            'convert': {
                'total': 1,
                'passed': 0,
                'failed': 1,
                'pass_rate': 0.0,
                'avg_rounds': 4.0
            },
            'env': {
                'total': 1,
                'passed': 0,
                'failed': 1,
                'pass_rate': 0.0,
                'avg_rounds': 3.0
            },
            'refactor': {
                'total': 1,
                'passed': 0,
                'failed': 1,
                'pass_rate': 0.0,
                'avg_rounds': 6.0
            },
            'split': {
                'total': 1,
                'passed': 0,
                'failed': 1,
                'pass_rate': 0.0,
                'avg_rounds': 4.0
            },
            'sum': {
                'total': 1,
                'passed': 1,
                'failed': 0,
                'pass_rate': 1.0,
                'avg_rounds': 9.0
            }
        }
    }
    
    print("\n" + "=" * 70)
    print("✅ 评测完成！")
    print("=" * 70)
    
    # 显示简洁的统计结果
    print(f"\n📊 总体结果:")
    print(f"  总任务数: {stats['total']}")
    print(f"  通过: {stats['passed']} ✓")
    print(f"  失败: {stats['failed']} ✗")
    print(f"  通过率: {stats['pass_rate']:.1%}")
    
    print(f"\n📈 执行统计:")
    print(f"  平均轮数: {stats['round_stats']['avg_rounds']:.1f}")
    print(f"  工具调用: {stats['tool_stats']['total_calls']} 次")
    
    print(f"\n🔍 各任务类型:")
    for task_type, task_stats in stats['by_task_type'].items():
        status = "✓" if task_stats['pass_rate'] == 1.0 else "✗"
        print(f"  {status} {task_type}: {task_stats['passed']}/{task_stats['total']} 通过")
    
    print("\n" + "=" * 70)
    print("\n💡 提示:")
    print("  - 详细日志: logs/__main__.log")
    print("  - 执行逻辑: docs/TASK_EXECUTION_FLOW.md")
    print("  - 失败原因分析请查看日志文件")
    print()


if __name__ == "__main__":
    print("\n🧪 测试简洁统计输出格式")
    print("=" * 70)
    test_output_format()
    
    print("\n✅ 对比:")
    print("\n【旧格式】（冗长）:")
    print("  logger.info(f'统计结果: {stats}')")
    print("  → 输出整个stats字典（200+行）")
    
    print("\n【新格式】（简洁）:")
    print("  只显示关键信息：")
    print("  - 总体结果（通过率）")
    print("  - 执行统计（轮数、工具调用）")
    print("  - 各任务类型结果")
    print("  → 只有10行左右")
    
    print("\n" + "=" * 70)
