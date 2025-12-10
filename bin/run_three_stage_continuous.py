#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三阶段连续评测系统

对同一个任务连续执行三个阶段：
1. 任务分解 - 将用户问题分解为子任务
2. 任务规划 - 对子任务进行排序和规划依赖关系
3. 任务执行 - 按照规划执行任务并验证结果

每个阶段的输入依赖于上一个阶段的输出
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple

# 添加lib目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.config_manager import get_config
from lib.core.logger import LoggerManager, get_logger
from lib.core.utils import read_json
from lib.core.output_control import set_show_details, print_detail
from lib.api.client import APIClient
from lib.validators.task_decomposition import validate_task_decomposition, extract_tasks_from_response
from lib.validators.task_planning import validate_task_planning
from lib.core.evaluation_engine import EvaluationEngine


def create_default_plan_from_dependencies(
    tasks: List[str],
    dependencies: Dict[str, List[str]]
) -> List[List[str]]:
    """
    根据依赖关系创建默认的执行计划
    
    使用拓扑排序算法
    
    Args:
        tasks: 任务列表
        dependencies: 依赖关系 {task: [prerequisite_tasks]}
    
    Returns:
        分层的执行计划 [[level1_tasks], [level2_tasks], ...]
    """
    # 构建依赖图
    task_deps = {task: dependencies.get(task, []) for task in tasks}
    
    # 计算每个任务的层级
    task_levels = {}
    
    def get_task_level(task: str) -> int:
        if task in task_levels:
            return task_levels[task]
        
        deps = task_deps.get(task, [])
        if not deps:
            task_levels[task] = 0
            return 0
        
        max_dep_level = max([get_task_level(dep) for dep in deps])
        task_levels[task] = max_dep_level + 1
        return task_levels[task]
    
    # 计算所有任务的层级
    for task in tasks:
        get_task_level(task)
    
    # 按层级分组
    max_level = max(task_levels.values()) if task_levels else 0
    plan = [[] for _ in range(max_level + 1)]
    
    for task, level in task_levels.items():
        plan[level].append(task)
    
    return plan


def print_banner():
    print("\n" + "="*70)
    print("           三阶段连续评测系统 v1.0")
    print("="*70)
    print("\n对同一个任务连续执行三个阶段：")
    print("  🔹 阶段1: 任务分解 - 分解用户问题为子任务")
    print("  🔹 阶段2: 任务规划 - 规划子任务的执行顺序和依赖")
    print("  🔹 阶段3: 任务执行 - 按照规划执行并验证结果")
    print("\n核心逻辑:")
    print("  ✓ 评测模型输出 - 每个阶段都评测模型的实际表现")
    print("  ✓ 传递ground_truth - 下一阶段使用标准答案作为输入")
    print("  ✓ 保证上下文稳定 - 避免错误信息的连锁传播")
    print("="*70 + "\n")


def run_decomposition_stage(
    test_case: Dict[str, Any],
    client: APIClient,
    config: Any
) -> Tuple[Dict[str, Any], List[str]]:
    """
    运行任务分解阶段
    
    Returns:
        (验证结果, 提取的任务列表)
    """
    logger = get_logger(__name__)
    logger.info("="*70)
    logger.info("阶段1：任务分解")
    logger.info("="*70)
    
    print("\n🔹 阶段1：任务分解")
    print("-" * 70)
    
    # 加载提示词
    system_prompt_file = config.paths.prompts_dir / "system_prompt_2.json"
    prompt_data = read_json(system_prompt_file)
    
    base_prompt = prompt_data.get('base', '')
    task_decomp = prompt_data.get('task', {}).get('task_decomposition', {})
    decomp_base = task_decomp.get('base', '')
    
    # 获取格式配置
    default_format = config.get('prompts.stages.decomposition.default_format', 'markdown')
    case_format = test_case.get('format', default_format)
    
    format_section = task_decomp.get('format', {})
    format_base = format_section.get('base', '\n输出格式要求：\n')
    format_template = format_section.get(case_format, '')
    
    system_prompt = base_prompt + "\n" + decomp_base + format_base + format_template
    
    # 调用模型
    user_question = test_case["initial_question"]
    logger.info(f"用户问题: {user_question}")
    print(f"用户问题: {user_question}")
    
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
    )
    
    model_response = response['choices'][0]['message']['content']
    logger.info(f"模型回复:\n{model_response}")
    
    # 详细输出（仅在启用时）
    print_detail(f"\n模型回复:\n{model_response}")
    
    # 提取任务
    extracted_tasks = extract_tasks_from_response(model_response, case_format)
    logger.info(f"提取到 {len(extracted_tasks)} 个任务")
    
    print(f"\n✅ 提取到 {len(extracted_tasks)} 个子任务")
    print_detail("\n子任务列表:")
    for i, task in enumerate(extracted_tasks, 1):
        print_detail(f"  {i}. {task}")
    
    # 验证
    use_llm_similarity = config.get('evaluation.task_decomposition.use_llm_similarity', True)
    similarity_threshold = config.get('evaluation.task_decomposition.similarity_threshold', 0.7)
    
    ground_truth = test_case["stages"]["decomposition"]["ground_truth"]
    
    validation_result = validate_task_decomposition(
        model_response=model_response,
        ground_truth=ground_truth,
        mode="open",
        format_type=case_format,
        similarity_threshold=similarity_threshold,
        use_llm_similarity=use_llm_similarity
    )
    
    print(f"\n验证结果:")
    print(f"  召回率: {validation_result['recall']:.2%}")
    print(f"  准确率: {validation_result['precision']:.2%}")
    print(f"  F1分数: {validation_result['f1_score']:.2%}")
    
    min_recall = test_case["stages"]["decomposition"].get("min_recall", 0.6)
    min_precision = test_case["stages"]["decomposition"].get("min_precision", 0.5)
    
    passed = (validation_result['recall'] >= min_recall and 
              validation_result['precision'] >= min_precision)
    
    validation_result['passed'] = passed
    validation_result['model_response'] = model_response
    validation_result['extracted_tasks'] = extracted_tasks
    
    if passed:
        print(f"  ✅ 通过 (召回率 >= {min_recall:.0%}, 准确率 >= {min_precision:.0%})")
    else:
        print(f"  ❌ 未通过 (要求: 召回率 >= {min_recall:.0%}, 准确率 >= {min_precision:.0%})")
    
    return validation_result, extracted_tasks


def run_planning_stage(
    test_case: Dict[str, Any],
    ground_truth_tasks: List[str],
    client: APIClient,
    config: Any
) -> Tuple[Dict[str, Any], List[List[str]]]:
    """
    运行任务规划阶段
    
    Args:
        ground_truth_tasks: 从阶段1的ground_truth得到的任务列表（不是模型输出！）
    
    Returns:
        (验证结果, 规划的任务顺序)
    """
    logger = get_logger(__name__)
    logger.info("="*70)
    logger.info("阶段2：任务规划")
    logger.info("="*70)
    
    print("\n🔹 阶段2：任务规划")
    print("-" * 70)
    print(f"输入: 阶段1的ground_truth任务列表 ({len(ground_truth_tasks)} 个)")
    print("注意: 使用ground_truth而不是模型输出，以保证上下文稳定性")
    
    # 加载提示词
    system_prompt_file = config.paths.prompts_dir / "system_prompt_2.json"
    prompt_data = read_json(system_prompt_file)
    
    base_prompt = prompt_data.get('base', '')
    task_planning = prompt_data.get('task', {}).get('task_planning', {})
    planning_base = task_planning.get('base', '')
    
    system_prompt = base_prompt + "\n" + planning_base
    
    # 构建用户消息：使用ground_truth任务列表
    user_message = "已拆解好的子任务列表：\n" + "\n".join([f"- {task}" for task in ground_truth_tasks])
    
    logger.info(f"用户消息:\n{user_message}")
    logger.info(f"输入来源: ground_truth (阶段1)")
    
    # 调用模型
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )
    
    model_response = response['choices'][0]['message']['content']
    logger.info(f"模型回复:\n{model_response}")
    
    print(f"\n✅ 规划完成")
    print_detail(f"\n模型规划结果:")
    print_detail(model_response)
    
    # 验证（使用ground_truth任务列表）
    dependencies = test_case["stages"]["planning"]["dependencies"]
    
    validation_result = validate_task_planning(
        model_response=model_response,
        ground_truth_tasks=ground_truth_tasks,  # 使用ground_truth任务列表
        dependencies=dependencies
    )
    
    print(f"\n验证结果:")
    print(f"  覆盖度: {validation_result['coverage']:.2%}")
    print(f"  顺序正确率: {validation_result['order_correctness']:.2%}")
    print(f"  层级效率: {validation_result['level_efficiency']:.2%}")
    print(f"  综合得分: {validation_result['overall_score']:.2%}")
    
    min_coverage = test_case["stages"]["planning"].get("min_coverage", 0.7)
    min_order = test_case["stages"]["planning"].get("min_order_correctness", 0.8)
    
    passed = (validation_result['coverage'] >= min_coverage and 
              validation_result['order_correctness'] >= min_order)
    
    validation_result['passed'] = passed
    validation_result['model_response'] = model_response
    validation_result['input_tasks'] = ground_truth_tasks
    validation_result['input_source'] = "ground_truth"
    
    if passed:
        print(f"  ✅ 通过")
    else:
        print(f"  ❌ 未通过")
    
    # 提取规划的任务顺序
    planned_order = validation_result.get('model_plan', [])
    
    return validation_result, planned_order


def run_execution_stage(
    test_case: Dict[str, Any],
    ground_truth_plan: List[List[str]],
    config: Any
) -> Dict[str, Any]:
    """
    运行任务执行阶段
    
    Args:
        ground_truth_plan: 从阶段2的ground_truth得到的任务执行计划（不是模型输出！）
    
    Returns:
        执行结果
    """
    logger = get_logger(__name__)
    logger.info("="*70)
    logger.info("阶段3：任务执行")
    logger.info("="*70)
    
    print("\n🔹 阶段3：任务执行")
    print("-" * 70)
    print(f"输入: 阶段2的ground_truth执行计划")
    print("注意: 使用ground_truth plan而不是模型输出，以保证上下文稳定性")
    
    task_data = test_case["task_data"]
    
    print(f"\n任务类型: {task_data['tag']}")
    print(f"\n执行计划:")
    for i, level in enumerate(ground_truth_plan, 1):
        print(f"  层级{i}: {level}")
    
    logger.info(f"输入计划: {ground_truth_plan}")
    logger.info(f"输入来源: ground_truth (阶段2)")
    
    # 构建question对象（从task_data）
    question = {
        "tag": task_data["tag"],
        "number": task_data["number"],
        "question": test_case["initial_question"],
        "answer": "我会按照以下步骤完成任务。",  # 添加answer字段
        "plan_answer": str(ground_truth_plan)  # 添加plan_answer字段
    }
    
    # 添加额外的验证字段
    if "test_case" in task_data:
        question["test_case"] = task_data["test_case"]
    if "names" in task_data:
        question["names"] = task_data["names"]
    if "function" in task_data:
        question["function"] = task_data["function"]
    if "sums" in task_data:
        question["sums"] = task_data["sums"]
    
    # 使用EvaluationEngine运行单个任务
    engine = EvaluationEngine(
        model=config.api.default_model,
        use_stream=config.api.stream_enabled
    )
    
    # 加载系统提示词和工具
    from lib.core.utils import read_json
    system_prompt_file = config.paths.prompts_dir / "system_prompt_2.json"
    tool_list_file = config.paths.prompts_dir / "tool_list.json"
    
    system_prompt_data = read_json(system_prompt_file)
    tools = read_json(tool_list_file)
    
    # 构建任务执行的系统提示词
    system_prompt = system_prompt_data['base']  # 基础提示词
    system_prompt += "\n" + system_prompt_data['task']['task_exe']['base']  # 任务执行提示词
    
    # 准备ground_truth（使用任务执行计划）
    ground_truth = {
        "question": test_case["initial_question"],  # 添加question字段
        "answer": "我会按照给定的任务列表来执行。",  # 模拟的answer
        "SubTasks": test_case["stages"]["decomposition"]["ground_truth"],
        "plan_answer": str(ground_truth_plan)
    }
    
    # 创建输出文件
    import time
    output_dir = config.paths.outputs_dir / f"exec_{int(time.time())}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"result_{task_data['number']}.json"
    
    # 运行单个任务
    print("\n开始执行任务...")
    try:
        result = engine.run_single_task(
            question=question,
            ground_truth=ground_truth,
            system_prompt=system_prompt,  # 使用构建好的system_prompt
            tools=tools,
            output_file=output_file
        )
        
        passed = result.get('pass', False)
        
        print(f"\n执行结果:")
        print(f"  任务: {question['tag']}_{question['number']}")
        print(f"  通过: {'✓' if passed else '✗'}")
        print(f"  轮次: {result.get('metrics', {}).get('total_rounds', 0)}")
        print(f"  工具调用: {result.get('metrics', {}).get('tool_calls', 0)}")
        
        if passed:
            print(f"  ✅ 通过")
        else:
            print(f"  ❌ 未通过")
            if 'error' in result:
                print(f"  错误: {result['error']}")
        
        return {
            'passed': passed,
            'task_result': result,
            'metrics': result.get('metrics', {}),
            'input_plan': ground_truth_plan,
            'input_source': 'ground_truth',
            'output_file': str(output_file)
        }
        
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        print(f"\n❌ 任务执行失败: {e}")
        return {
            'passed': False,
            'error': str(e),
            'input_plan': ground_truth_plan,
            'input_source': 'ground_truth'
        }


def run_batch_evaluation(
    test_cases: List[Dict[str, Any]],
    client: APIClient,
    config: Any
) -> List[Dict[str, Any]]:
    """
    批量处理模式：按阶段批量处理所有测试用例
    
    优点：
    - 更快的执行速度（可以一次性看到所有阶段1的结果）
    - 便于调试和分析（同一阶段的结果集中显示）
    
    逻辑：
    - 阶段1：批量处理所有测试用例的分解阶段
    - 阶段2：批量处理所有测试用例的规划阶段（使用阶段1的ground_truth）
    - 阶段3：批量处理所有测试用例的执行阶段（使用阶段2的ground_truth）
    
    Args:
        test_cases: 测试用例列表
        client: API客户端
        config: 配置对象
    
    Returns:
        评测结果列表
    """
    logger = get_logger(__name__)
    all_results = []
    
    # 初始化每个测试用例的结果结构
    for test_case in test_cases:
        all_results.append({
            "test_case_id": test_case['id'],
            "test_case_name": test_case['name'],
            "stages": {}
        })
    
    print(f"\n📦 批量处理模式: 将按阶段批量处理 {len(test_cases)} 个测试用例")
    print(f"  优势: 更快的执行速度，便于对比同一阶段的所有结果\n")
    
    # ========== 阶段1：批量处理任务分解 ==========
    print(f"\n{'='*70}")
    print(f"阶段 1/3: 任务分解 - 批量处理 {len(test_cases)} 个测试用例")
    print(f"{'='*70}\n")
    
    decomp_results = []
    ground_truth_tasks_list = []
    
    for i, test_case in enumerate(test_cases):
        print(f"[{i+1}/{len(test_cases)}] {test_case['name']}")
        
        try:
            decomp_result, extracted_tasks = run_decomposition_stage(test_case, client, config)
            decomp_results.append(decomp_result)
            
            # 获取ground_truth任务列表（用于传递给阶段2）
            ground_truth_tasks = test_case["stages"]["decomposition"]["ground_truth"]
            ground_truth_tasks_list.append(ground_truth_tasks)
            
            all_results[i]["stages"]["decomposition"] = decomp_result
            
            print(f"  模型输出: {len(extracted_tasks)} 个任务")
            print(f"  Ground Truth: {len(ground_truth_tasks)} 个任务")
            print(f"  评测结果: {'✅ 通过' if decomp_result['passed'] else '❌ 未通过'}")
            print(f"  F1分数: {decomp_result['f1_score']:.2%}\n")
            
        except Exception as e:
            logger.error(f"测试用例 {test_case['name']} 分解阶段失败: {e}", exc_info=True)
            print(f"  ❌ 失败: {e}\n")
            decomp_results.append({"error": str(e), "passed": False})
            ground_truth_tasks_list.append([])
    
    print(f"\n📊 阶段1汇总:")
    passed_count = sum(1 for r in decomp_results if r.get('passed', False))
    print(f"  通过率: {passed_count}/{len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    
    # ========== 阶段2：批量处理任务规划 ==========
    print(f"\n{'='*70}")
    print(f"阶段 2/3: 任务规划 - 批量处理 {len(test_cases)} 个测试用例")
    print(f"{'='*70}\n")
    
    planning_results = []
    ground_truth_plans_list = []
    
    for i, test_case in enumerate(test_cases):
        print(f"[{i+1}/{len(test_cases)}] {test_case['name']}")
        
        # 使用阶段1的ground_truth作为输入
        ground_truth_tasks = ground_truth_tasks_list[i]
        
        if not ground_truth_tasks:
            print(f"  ⚠️  跳过（阶段1失败）\n")
            planning_results.append({"error": "阶段1失败", "passed": False})
            ground_truth_plans_list.append([])
            continue
        
        try:
            planning_result, planned_order = run_planning_stage(
                test_case,
                ground_truth_tasks,  # ← 使用ground_truth
                client,
                config
            )
            planning_results.append(planning_result)
            
            # 获取ground_truth计划（用于传递给阶段3）
            if "ground_truth_plan" in test_case["stages"]["planning"]:
                ground_truth_plan = test_case["stages"]["planning"]["ground_truth_plan"]
            else:
                ground_truth_plan = create_default_plan_from_dependencies(
                    ground_truth_tasks,
                    test_case["stages"]["planning"]["dependencies"]
                )
            ground_truth_plans_list.append(ground_truth_plan)
            
            all_results[i]["stages"]["planning"] = planning_result
            
            print(f"  输入: ground_truth ({len(ground_truth_tasks)} 个任务)")
            print(f"  模型输出: {len(planned_order)} 层计划")
            print(f"  Ground Truth: {len(ground_truth_plan)} 层计划")
            print(f"  评测结果: {'✅ 通过' if planning_result['passed'] else '❌ 未通过'}")
            print(f"  综合得分: {planning_result['overall_score']:.2%}\n")
            
        except Exception as e:
            logger.error(f"测试用例 {test_case['name']} 规划阶段失败: {e}", exc_info=True)
            print(f"  ❌ 失败: {e}\n")
            planning_results.append({"error": str(e), "passed": False})
            ground_truth_plans_list.append([])
    
    print(f"\n📊 阶段2汇总:")
    passed_count = sum(1 for r in planning_results if r.get('passed', False))
    print(f"  通过率: {passed_count}/{len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    
    # ========== 阶段3：批量处理任务执行 ==========
    print(f"\n{'='*70}")
    print(f"阶段 3/3: 任务执行 - 批量处理 {len(test_cases)} 个测试用例")
    print(f"{'='*70}\n")
    
    execution_results = []
    
    for i, test_case in enumerate(test_cases):
        print(f"[{i+1}/{len(test_cases)}] {test_case['name']}")
        
        # 使用阶段2的ground_truth作为输入
        ground_truth_plan = ground_truth_plans_list[i]
        
        if not ground_truth_plan:
            print(f"  ⚠️  跳过（阶段2失败）\n")
            execution_results.append({"error": "阶段2失败", "passed": False})
            continue
        
        try:
            execution_result = run_execution_stage(
                test_case,
                ground_truth_plan,  # ← 使用ground_truth
                config
            )
            execution_results.append(execution_result)
            
            all_results[i]["stages"]["execution"] = execution_result
            
            print(f"  输入: ground_truth ({len(ground_truth_plan)} 层计划)")
            print(f"  评测结果: {'✅ 通过' if execution_result['passed'] else '❌ 未通过'}\n")
            
        except Exception as e:
            logger.error(f"测试用例 {test_case['name']} 执行阶段失败: {e}", exc_info=True)
            print(f"  ❌ 失败: {e}\n")
            execution_results.append({"error": str(e), "passed": False})
    
    print(f"\n📊 阶段3汇总:")
    passed_count = sum(1 for r in execution_results if r.get('passed', False))
    print(f"  通过率: {passed_count}/{len(test_cases)} ({passed_count/len(test_cases)*100:.1f}%)")
    
    # ========== 整体汇总 ==========
    print(f"\n{'='*70}")
    print(f"批量处理完成 - 整体汇总")
    print(f"{'='*70}\n")
    
    for i, result in enumerate(all_results):
        decomp_passed = result["stages"].get("decomposition", {}).get("passed", False)
        planning_passed = result["stages"].get("planning", {}).get("passed", False)
        execution_passed = result["stages"].get("execution", {}).get("passed", False)
        
        all_passed = decomp_passed and planning_passed and execution_passed
        
        result["overall"] = {
            "all_stages_passed": all_passed,
            "summary": f"分解: {'✅' if decomp_passed else '❌'} | "
                      f"规划: {'✅' if planning_passed else '❌'} | "
                      f"执行: {'✅' if execution_passed else '❌'}"
        }
        
        print(f"[{i+1}] {result['test_case_name']}")
        print(f"    {result['overall']['summary']}")
    
    total_passed = sum(1 for r in all_results if r["overall"]["all_stages_passed"])
    print(f"\n📈 总体通过率: {total_passed}/{len(test_cases)} ({total_passed/len(test_cases)*100:.1f}%)")
    
    return all_results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="三阶段连续评测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--test-file",
        default="data/three_stage_test_cases.json",
        help="测试用例文件路径"
    )
    
    parser.add_argument(
        "--test-id",
        help="指定测试用例ID"
    )
    
    parser.add_argument(
        "--model",
        help="指定模型名称"
    )
    
    parser.add_argument(
        "--output",
        help="结果输出文件路径"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="批量处理模式（一次性处理所有测试用例的同一阶段，速度更快）"
    )
    
    parser.add_argument(
        "--show-details",
        action="store_true",
        help="显示详细信息（包括模型输出、代码内容等，默认不显示）"
    )
    
    args = parser.parse_args()
    
    # 设置输出控制
    set_show_details(args.show_details)
    
    # 打印欢迎信息
    print_banner()
    
    if not args.show_details:
        print("\n💡 提示: 使用 --show-details 查看模型输出和代码内容")
        print("   所有详细信息已保存到日志文件中\n")
    
    # 加载配置
    try:
        config = get_config()
        LoggerManager.initialize(config.paths.logs_dir)
        logger = get_logger(__name__)
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return 1
    
    # 加载测试用例
    test_file = Path(args.test_file)
    if not test_file.exists():
        print(f"❌ 测试文件不存在: {test_file}")
        return 1
    
    with open(test_file, 'r', encoding='utf-8') as f:
        test_cases = json.load(f)
    
    if args.test_id:
        test_cases = [tc for tc in test_cases if tc['id'] == args.test_id]
        if not test_cases:
            print(f"❌ 未找到测试用例: {args.test_id}")
            return 1
    
    # 初始化API客户端
    model = args.model or config.api.default_model
    client = APIClient(model=model)
    
    # 根据模式选择处理方式
    if args.batch:
        # 批量处理模式
        print("\n🚀 使用批量处理模式")
        print("  特点: 按阶段批量处理，速度更快，便于对比同一阶段的所有结果\n")
        all_results = run_batch_evaluation(test_cases, client, config)
    else:
        # 逐个处理模式（默认）
        print("\n🔄 使用逐个处理模式")
        print("  特点: 每个测试用例连续完成三个阶段，便于跟踪单个用例的完整流程\n")
        all_results = []
        
        for test_case in test_cases:
            print(f"\n{'='*70}")
            print(f"测试用例: {test_case['name']}")
            print(f"描述: {test_case['description']}")
            print(f"{'='*70}")
            
            result = {
                "test_case_id": test_case['id'],
                "test_case_name": test_case['name'],
                "stages": {}
            }
            
            try:
                # 阶段1：任务分解
                decomp_result, extracted_tasks = run_decomposition_stage(test_case, client, config)
                result["stages"]["decomposition"] = decomp_result
                
                # 获取ground_truth任务列表（用于传递给阶段2）
                ground_truth_tasks = test_case["stages"]["decomposition"]["ground_truth"]
                
                print(f"\n📋 上下文传递：")
                print(f"  阶段1模型输出: {len(extracted_tasks)} 个任务 → 仅用于评测")
                print(f"  传递给阶段2: ground_truth ({len(ground_truth_tasks)} 个任务)")
                logger.info(f"阶段1完成，传递ground_truth给阶段2: {ground_truth_tasks}")
                
                # 阶段2：任务规划（使用ground_truth任务列表）
                planning_result, planned_order = run_planning_stage(
                    test_case, 
                    ground_truth_tasks,  # ← 传递ground_truth，不是extracted_tasks！
                    client, 
                    config
                )
                result["stages"]["planning"] = planning_result
                
                # 获取ground_truth计划（用于传递给阶段3）
                # 如果测试用例中有ground_truth_plan，使用它；否则创建默认计划
                if "ground_truth_plan" in test_case["stages"]["planning"]:
                    ground_truth_plan = test_case["stages"]["planning"]["ground_truth_plan"]
                else:
                    # 根据依赖关系创建默认的ground_truth计划
                    ground_truth_plan = create_default_plan_from_dependencies(
                        ground_truth_tasks,
                        test_case["stages"]["planning"]["dependencies"]
                    )
                
                print(f"\n📋 上下文传递：")
                print(f"  阶段2模型输出: {len(planned_order)} 层计划 → 仅用于评测")
                print(f"  传递给阶段3: ground_truth plan ({len(ground_truth_plan)} 层)")
                logger.info(f"阶段2完成，传递ground_truth plan给阶段3: {ground_truth_plan}")
                
                # 阶段3：任务执行（使用ground_truth计划）
                execution_result = run_execution_stage(
                    test_case, 
                    ground_truth_plan,  # ← 传递ground_truth plan，不是planned_order！
                    config
                )
                result["stages"]["execution"] = execution_result
                
                # 整体评价
                result["overall"] = {
                    "all_stages_passed": all([
                        decomp_result['passed'],
                        planning_result['passed'],
                        execution_result['passed']
                    ]),
                    "summary": f"分解: {'✅' if decomp_result['passed'] else '❌'} | "
                              f"规划: {'✅' if planning_result['passed'] else '❌'} | "
                              f"执行: {'✅' if execution_result['passed'] else '❌'}"
                }
                
                print(f"\n{'='*70}")
                print(f"整体结果: {result['overall']['summary']}")
                print(f"{'='*70}")
                
            except Exception as e:
                logger.error(f"评测失败: {e}", exc_info=True)
                print(f"\n❌ 评测失败: {e}")
                result["error"] = str(e)
            
            all_results.append(result)
    
    # 汇总统计
    print("\n" + "="*70)
    print("📊 三阶段评测汇总统计")
    print("="*70)
    
    total_cases = len(all_results)
    
    # 统计各阶段
    decomp_passed = sum(1 for r in all_results if r.get("stages", {}).get("decomposition", {}).get("passed", False))
    planning_passed = sum(1 for r in all_results if r.get("stages", {}).get("planning", {}).get("passed", False))
    execution_passed = sum(1 for r in all_results if r.get("stages", {}).get("execution", {}).get("passed", False))
    all_stages_passed = sum(1 for r in all_results if r.get("overall", {}).get("all_stages_passed", False))
    
    # 计算平均分数
    decomp_scores = [r.get("stages", {}).get("decomposition", {}).get("metrics", {}).get("overall_score", 0) 
                     for r in all_results if "stages" in r and "decomposition" in r["stages"]]
    planning_scores = [r.get("stages", {}).get("planning", {}).get("metrics", {}).get("overall_score", 0) 
                       for r in all_results if "stages" in r and "planning" in r["stages"]]
    
    avg_decomp = sum(decomp_scores) / len(decomp_scores) if decomp_scores else 0
    avg_planning = sum(planning_scores) / len(planning_scores) if planning_scores else 0
    
    print(f"\n总测试用例数: {total_cases}")
    print(f"\n各阶段通过情况:")
    print(f"  阶段1 (任务分解): {decomp_passed}/{total_cases} 通过 ({decomp_passed/total_cases*100:.1f}%)")
    print(f"    - 平均综合得分: {avg_decomp:.2%}")
    print(f"  阶段2 (任务规划): {planning_passed}/{total_cases} 通过 ({planning_passed/total_cases*100:.1f}%)")
    print(f"    - 平均综合得分: {avg_planning:.2%}")
    print(f"  阶段3 (任务执行): {execution_passed}/{total_cases} 通过 ({execution_passed/total_cases*100:.1f}%)")
    print(f"\n完整流程通过: {all_stages_passed}/{total_cases} ({all_stages_passed/total_cases*100:.1f}%)")
    
    # 详细结果列表
    print(f"\n详细结果:")
    for i, r in enumerate(all_results, 1):
        case_name = r.get("test_case_name", f"Test {i}")
        overall = r.get("overall", {})
        summary = overall.get("summary", "N/A")
        print(f"  {i}. {case_name}")
        print(f"     {summary}")
    
    # 保存结果
    if args.output:
        output_file = Path(args.output)
    else:
        import time
        timestamp = int(time.time())
        output_file = config.paths.outputs_dir / f"three_stage_{timestamp}.json"
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 详细结果已保存到: {output_file}")
    
    LoggerManager.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
