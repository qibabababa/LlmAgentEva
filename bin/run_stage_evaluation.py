#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三阶段评测系统 - 交互式主入口

支持评测三个阶段:
1. 任务分解 (Task Decomposition) - 评估召回率和准确率
2. 任务规划 (Task Planning) - 评估覆盖度和顺序正确性
3. 任务执行 (Task Execution) - 评估最终结果是否通过

用户可以选择评测单个阶段、多个阶段或全流程
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

# 添加lib目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.config_manager import get_config
from lib.core.logger import LoggerManager, get_logger
from lib.validators.task_decomposition import validate_task_decomposition
from lib.validators.task_planning import validate_task_planning
from lib.core.evaluation_engine import EvaluationEngine
from lib.api.client import APIClient


def print_banner():
    print("\n" + "="*70)
    print("                    三阶段评测系统 v1.0")
    print("="*70)
    print("\n本系统支持三个评测阶段:")
    print("  1️⃣  任务分解 (Task Decomposition) - 评估任务拆分能力")
    print("  2️⃣  任务规划 (Task Planning) - 评估任务排序和依赖管理")
    print("  3️⃣  任务执行 (Task Execution) - 评估最终执行结果")
    print("="*70 + "\n")


def select_stages() -> List[str]:
    """
    交互式选择要评测的阶段
    
    Returns:
        选中的阶段列表
    """
    print("请选择要评测的阶段（可多选）:")
    print("  [1] 任务分解 (Decomposition)")
    print("  [2] 任务规划 (Planning)")
    print("  [3] 任务执行 (Execution)")
    print("  [4] 全流程 (All)")
    print("  [0] 退出\n")
    
    while True:
        choice = input("请输入选项 (例如: 1 或 123 或 4): ").strip()
        
        if choice == '0':
            print("退出评测系统。")
            sys.exit(0)
        
        if choice == '4':
            return ['decomposition', 'planning', 'execution']
        
        stages = []
        for c in choice:
            if c == '1':
                stages.append('decomposition')
            elif c == '2':
                stages.append('planning')
            elif c == '3':
                stages.append('execution')
        
        if stages:
            return stages
        
        print("❌ 无效输入，请重新选择。\n")


def run_decomposition_evaluation(test_cases: List[Dict[str, Any]], model: str = None) -> Dict[str, Any]:
    """
    运行任务分解评测
    
    Args:
        test_cases: 测试用例列表
        model: 模型名称（可选）
        
    Returns:
        评测结果统计
    """
    logger = get_logger(__name__)
    logger.info("开始任务分解评测")
    
    print("\n" + "="*70)
    print("阶段 1: 任务分解评测")
    print("="*70)
    
    # 初始化 API 客户端
    config = get_config()
    client = APIClient(model=model or config.api.default_model)
    print(f"使用模型: {client.model}\n")
    
    # 加载 system_prompt_2.json
    from lib.core.utils import read_json
    system_prompt_file = config.paths.prompts_dir / "system_prompt_2.json"
    prompt_data = read_json(system_prompt_file)
    
    # 构建任务分解的系统提示词
    base_prompt = prompt_data.get('base', '')
    task_decomp = prompt_data.get('task', {}).get('task_decomposition', {})
    decomp_base = task_decomp.get('base', '')
    
    # 从配置读取默认格式
    default_format = config.get('prompts.stages.decomposition.default_format', 'markdown')
    logger.info(f"任务分解默认格式: {default_format}")
    
    # 从配置读取相似度判断设置
    use_llm_similarity = config.get('evaluation.task_decomposition.use_llm_similarity', True)
    similarity_threshold = config.get('evaluation.task_decomposition.similarity_threshold', 0.7)
    
    logger.info(f"使用LLM语义相似度判断: {use_llm_similarity}, 阈值: {similarity_threshold}")
    
    results = []
    total_recall = 0.0
    total_precision = 0.0
    total_f1 = 0.0
    
    for i, case in enumerate(test_cases):
        if case.get('stage') != 'decomposition':
            continue
        
        print(f"\n[{i+1}] 评测用例: {case.get('name', f'Case {i+1}')}")
        
        # 根据测试用例的 mode 和 format 选择合适的提示词
        case_mode = case.get('mode', 'open')
        case_format = case.get('format', default_format)  # 测试用例可以指定格式
        
        logger.info(f"用例模式: {case_mode}, 输出格式: {case_format}")
        
        # 根据 mode 选择基础提示词
        if case_mode == 'constrained':
            # 全集模式：从提供的任务集合中选择
            mode_base = task_decomp.get('all_tasks', decomp_base)
            format_section = task_decomp.get('format_all', {})
        else:
            # 开放模式：自由分解
            mode_base = decomp_base
            format_section = task_decomp.get('format', {})
        
        # 获取格式模板
        format_base = format_section.get('base', '\n输出格式要求：\n')
        format_template = format_section.get(case_format, '')
        
        if not format_template:
            logger.warning(f"未找到格式 {case_format} 的模板，使用默认格式")
            format_template = format_section.get(default_format, '')
        
        # 构建完整的系统提示词
        system_prompt = base_prompt + "\n" + mode_base + format_base + format_template
        
        # 使用测试用例中的 user_question
        user_question = case.get('user_question', '')
        
        logger.info(f"正在调用模型进行任务分解: {case.get('name')}")
        
        try:
            # 调用 API 获取模型回复
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_question}
                ]
            )
            
            model_response = response['choices'][0]['message']['content']
            logger.info(f"模型原始回复:\n{model_response}")
            
        except Exception as e:
            logger.error(f"API 调用失败: {e}")
            print(f"  ❌ API 调用失败: {e}")
            continue
        
        # 验证结果 - 使用配置中的设置
        result = validate_task_decomposition(
            model_response=model_response,
            ground_truth=case['ground_truth'],
            mode=case_mode,
            format_type=case_format,
            similarity_threshold=similarity_threshold,
            use_llm_similarity=use_llm_similarity
        )
        
        # 记录详细的提取和验证信息
        logger.info(f"提取的任务数量: {result.get('num_model_output', 0)}")
        logger.info(f"提取的任务列表: {result.get('model_tasks', [])}")
        logger.info(f"标准答案: {case['ground_truth']}")
        logger.info(f"匹配的任务对: {result.get('matched_pairs', [])}")
        logger.info(f"遗漏的任务: {result.get('missed_tasks', [])}")
        logger.info(f"多余的任务: {result.get('extra_tasks', [])}")
        
        print(f"  召回率 (Recall):    {result['recall']:.2%}")
        print(f"  准确率 (Precision): {result['precision']:.2%}")
        print(f"  F1 分数:           {result['f1_score']:.2%}")
        
        if result.get('missed_tasks'):
            print(f"  ⚠️  遗漏任务: {len(result['missed_tasks'])} 个")
        
        # 保存模型回复到结果中
        result['model_response'] = model_response
        result['case_name'] = case.get('name')
        
        results.append(result)
        total_recall += result['recall']
        total_precision += result['precision']
        total_f1 += result['f1_score']
        
        logger.info(f"用例 {i+1}: 召回={result['recall']:.2%}, 准确={result['precision']:.2%}")
    
    num_cases = len(results)
    if num_cases == 0:
        print("\n⚠️  没有找到任务分解的测试用例")
        return {}
    
    summary = {
        'stage': 'decomposition',
        'total_cases': num_cases,
        'avg_recall': total_recall / num_cases,
        'avg_precision': total_precision / num_cases,
        'avg_f1_score': total_f1 / num_cases,
        'results': results
    }
    
    print("\n" + "-"*70)
    print("📊 任务分解评测汇总:")
    print(f"  测试用例数: {num_cases}")
    print(f"  平均召回率: {summary['avg_recall']:.2%}")
    print(f"  平均准确率: {summary['avg_precision']:.2%}")
    print(f"  平均F1分数: {summary['avg_f1_score']:.2%}")
    
    logger.info(f"任务分解评测完成: 平均F1={summary['avg_f1_score']:.2%}")
    
    return summary


def run_planning_evaluation(test_cases: List[Dict[str, Any]], model: str = None) -> Dict[str, Any]:
    """
    运行任务规划评测
    
    Args:
        test_cases: 测试用例列表
        model: 模型名称（可选）
        
    Returns:
        评测结果统计
    """
    logger = get_logger(__name__)
    logger.info("开始任务规划评测")
    
    print("\n" + "="*70)
    print("阶段 2: 任务规划评测")
    print("="*70)
    
    # 初始化 API 客户端
    config = get_config()
    client = APIClient(model=model or config.api.default_model)
    print(f"使用模型: {client.model}\n")
    
    # 加载 system_prompt_2.json
    from lib.core.utils import read_json
    system_prompt_file = config.paths.prompts_dir / "system_prompt_2.json"
    prompt_data = read_json(system_prompt_file)
    
    # 构建任务规划的系统提示词
    base_prompt = prompt_data.get('base', '')
    task_planning = prompt_data.get('task', {}).get('task_planning', {})
    planning_base = task_planning.get('base', '')
    
    system_prompt = base_prompt + "\n" + planning_base
    
    results = []
    total_coverage = 0.0
    total_order = 0.0
    total_overall = 0.0
    
    for i, case in enumerate(test_cases):
        if case.get('stage') != 'planning':
            continue
        
        print(f"\n[{i+1}] 评测用例: {case.get('name', f'Case {i+1}')}")
        
        # 构造用户消息：给出任务列表
        tasks = case.get('ground_truth_tasks', [])
        user_message = "已拆解好的子任务列表：\n" + "\n".join([f"- {task}" for task in tasks])
        
        logger.info(f"正在调用模型进行任务规划: {case.get('name')}")
        
        try:
            # 调用 API 获取模型回复
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            
            model_response = response['choices'][0]['message']['content']
            logger.debug(f"模型回复: {model_response[:200]}...")
            
        except Exception as e:
            logger.error(f"API 调用失败: {e}")
            print(f"  ❌ API 调用失败: {e}")
            continue
        
        # 验证结果
        result = validate_task_planning(
            model_response=model_response,
            ground_truth_tasks=case['ground_truth_tasks'],
            dependencies=case.get('dependencies')
        )
        
        print(f"  覆盖度 (Coverage):          {result['coverage']:.2%}")
        print(f"  顺序正确率 (Order):         {result['order_correctness']:.2%}")
        print(f"  层级效率 (Efficiency):      {result['level_efficiency']:.2%}")
        print(f"  综合得分 (Overall):         {result['overall_score']:.2%}")
        
        violations = result.get('detailed_results', {}).get('order', {}).get('violations', [])
        if violations:
            print(f"  ⚠️  依赖违反: {len(violations)} 个")
        
        # 保存模型回复到结果中
        result['model_response'] = model_response
        result['case_name'] = case.get('name')
        
        results.append(result)
        total_coverage += result['coverage']
        total_order += result['order_correctness']
        total_overall += result['overall_score']
        
        logger.info(f"用例 {i+1}: 覆盖={result['coverage']:.2%}, 顺序={result['order_correctness']:.2%}")
    
    num_cases = len(results)
    if num_cases == 0:
        print("\n⚠️  没有找到任务规划的测试用例")
        return {}
    
    summary = {
        'stage': 'planning',
        'total_cases': num_cases,
        'avg_coverage': total_coverage / num_cases,
        'avg_order_correctness': total_order / num_cases,
        'avg_overall_score': total_overall / num_cases,
        'results': results
    }
    
    print("\n" + "-"*70)
    print("📊 任务规划评测汇总:")
    print(f"  测试用例数: {num_cases}")
    print(f"  平均覆盖度: {summary['avg_coverage']:.2%}")
    print(f"  平均顺序正确率: {summary['avg_order_correctness']:.2%}")
    print(f"  平均综合得分: {summary['avg_overall_score']:.2%}")
    
    logger.info(f"任务规划评测完成: 平均得分={summary['avg_overall_score']:.2%}")
    
    return summary


def run_execution_evaluation(task_type: str, model: str, use_stream: bool) -> Dict[str, Any]:
    """
    运行任务执行评测
    
    Args:
        task_type: 任务类型
        model: 模型名称
        use_stream: 是否使用流式API
        
    Returns:
        评测结果统计
    """
    logger = get_logger(__name__)
    logger.info("开始任务执行评测")
    
    print("\n" + "="*70)
    print("阶段 3: 任务执行评测")
    print("="*70)
    
    print(f"\n任务类型: {task_type}")
    print(f"模型: {model}")
    print(f"流式模式: {'启用' if use_stream else '禁用'}")
    
    # 创建评测引擎
    engine = EvaluationEngine(model=model, use_stream=use_stream)
    
    # 运行评测
    stats = engine.run_evaluation(task_type=task_type)
    
    print("\n" + "-"*70)
    print("📊 任务执行评测汇总:")
    print(f"  总任务数: {stats['total']}")
    print(f"  通过: {stats['passed']} ✓")
    print(f"  失败: {stats['failed']} ✗")
    print(f"  通过率: {stats['pass_rate']:.1%}")
    
    logger.info(f"任务执行评测完成: 通过率={stats['pass_rate']:.1%}")
    
    return stats


def load_test_cases(file_path: str) -> List[Dict[str, Any]]:
    """
    从JSON文件加载测试用例
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        测试用例列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            return [data]
        return data
    except Exception as e:
        print(f"❌ 加载测试用例失败: {e}")
        return []


def save_results(results: Dict[str, Any], output_path: str):
    """
    保存评测结果到JSON文件
    
    Args:
        results: 评测结果
        output_path: 输出文件路径
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 结果已保存到: {output_file}")
    except Exception as e:
        print(f"❌ 保存结果失败: {e}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="三阶段评测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互式选择阶段
  python bin/run_stage_evaluation.py
  
  # 直接指定阶段
  python bin/run_stage_evaluation.py --stages decomposition planning
  
  # 评测全流程
  python bin/run_stage_evaluation.py --stages all
  
  # 指定测试用例文件
  python bin/run_stage_evaluation.py --test-file data/test_cases.json
  
  # 任务执行阶段指定任务类型
  python bin/run_stage_evaluation.py --stages execution --task-type fix_bug
        """
    )
    
    parser.add_argument(
        "--stages",
        nargs='+',
        choices=['decomposition', 'planning', 'execution', 'all'],
        help="要评测的阶段（可多个，用空格分隔）"
    )
    
    parser.add_argument(
        "--test-file",
        help="测试用例JSON文件路径"
    )
    
    parser.add_argument(
        "--task-type",
        choices=["fix_bug", "convert", "refactor", "env", "sum", "split", "all"],
        default="all",
        help="任务执行阶段的任务类型（默认: all）"
    )
    
    parser.add_argument(
        "--model",
        help="模型名称"
    )
    
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="禁用流式API"
    )
    
    parser.add_argument(
        "--output",
        help="结果输出文件路径"
    )
    
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="非交互模式（必须指定--stages）"
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 打印欢迎横幅
    print_banner()
    
    # 加载配置
    try:
        config = get_config()
        LoggerManager.initialize(config.paths.logs_dir)
        logger = get_logger(__name__)
        logger.info("="*70)
        logger.info("三阶段评测系统启动")
        logger.info("="*70)
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return 1
    
    # 确定要评测的阶段
    if args.stages:
        if 'all' in args.stages:
            selected_stages = ['decomposition', 'planning', 'execution']
        else:
            selected_stages = args.stages
    elif args.non_interactive:
        print("❌ 非交互模式必须指定 --stages 参数")
        return 1
    else:
        selected_stages = select_stages()
    
    print(f"\n✅ 将评测以下阶段: {', '.join(selected_stages)}")
    logger.info(f"选择的评测阶段: {selected_stages}")
    
    # 准备结果容器
    all_results = {
        'stages': selected_stages,
        'results': {}
    }
    
    # 加载测试用例（用于任务分解和规划）
    test_cases = []
    if 'decomposition' in selected_stages or 'planning' in selected_stages:
        if args.test_file:
            test_cases = load_test_cases(args.test_file)
            if not test_cases:
                print(f"⚠️  未能从 {args.test_file} 加载测试用例")
        else:
            # 使用默认测试用例路径
            default_file = config.paths.data_dir / "stage_test_cases.json"
            if default_file.exists():
                test_cases = load_test_cases(str(default_file))
            else:
                print(f"⚠️  未找到测试用例文件: {default_file}")
                print(f"   请使用 --test-file 指定测试用例文件")
    
    # 运行各阶段评测
    try:
        # 获取模型名称
        model = args.model or config.api.default_model
        
        # 阶段1: 任务分解
        if 'decomposition' in selected_stages:
            decomp_results = run_decomposition_evaluation(test_cases, model=model)
            if decomp_results:
                all_results['results']['decomposition'] = decomp_results
        
        # 阶段2: 任务规划
        if 'planning' in selected_stages:
            planning_results = run_planning_evaluation(test_cases, model=model)
            if planning_results:
                all_results['results']['planning'] = planning_results
        
        # 阶段3: 任务执行
        if 'execution' in selected_stages:
            use_stream = config.api.stream_enabled and not args.no_stream
            
            execution_results = run_execution_evaluation(
                task_type=args.task_type,
                model=model,
                use_stream=use_stream
            )
            all_results['results']['execution'] = execution_results
        
        # 显示总体总结
        print("\n" + "="*70)
        print("🎉 评测完成！")
        print("="*70)
        
        print("\n📊 总体总结:")
        for stage in selected_stages:
            if stage in all_results['results']:
                result = all_results['results'][stage]
                
                if stage == 'decomposition':
                    print(f"\n  任务分解:")
                    print(f"    平均F1分数: {result['avg_f1_score']:.2%}")
                
                elif stage == 'planning':
                    print(f"\n  任务规划:")
                    print(f"    平均综合得分: {result['avg_overall_score']:.2%}")
                
                elif stage == 'execution':
                    print(f"\n  任务执行:")
                    print(f"    通过率: {result['pass_rate']:.1%}")
        
        # 保存结果
        if args.output:
            save_results(all_results, args.output)
        else:
            # 默认保存到outputs目录
            import time
            timestamp = int(time.time())
            output_path = config.paths.outputs_dir / f"stage_eval_{timestamp}.json"
            save_results(all_results, str(output_path))
        
        logger.info("评测完成")
        LoggerManager.shutdown()
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  评测被用户中断")
        logger.warning("评测被用户中断")
        LoggerManager.shutdown()
        return 130
    
    except Exception as e:
        print(f"\n❌ 评测失败: {e}")
        logger.error(f"评测失败: {e}")
        import traceback
        traceback.print_exc()
        LoggerManager.shutdown()
        return 1


if __name__ == "__main__":
    sys.exit(main())
