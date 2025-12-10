#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务规划验证器

评估模型在任务规划阶段的表现：
1. 集合覆盖度 (Coverage): 规划中包含了多少标准答案中的任务
2. 顺序正确性 (Order): 任务之间的依赖关系和顺序是否正确

规划格式: [[task1, task2], [task3], [task4, task5]]
- 外层列表表示时间/顺序层级
- 内层列表中的元素可并行执行
"""

import re
import json
import ast
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path

from lib.core.logger import get_logger
from lib.validators.task_decomposition import (
    normalize_task, 
    calculate_similarity,
    calculate_similarity_llm_batch,
    calculate_similarity_rule_based
)

logger = get_logger(__name__)


def extract_planning_from_response(response: str) -> Optional[List[List[str]]]:
    """
    从模型响应中提取任务规划
    
    期望格式: [[task1, task2], [task3], [task4, task5]]
    
    Returns:
        规划列表，如果提取失败则返回None
    """
    try:
        # 1. 尝试直接用ast.literal_eval解析
        # 查找列表模式
        list_pattern = r'\[\s*\[.*?\]\s*(?:,\s*\[.*?\]\s*)*\]'
        matches = re.findall(list_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                planning = ast.literal_eval(match)
                # 验证格式
                if isinstance(planning, list) and all(isinstance(level, list) for level in planning):
                    # 确保所有元素都是字符串
                    valid = True
                    for level in planning:
                        if not all(isinstance(task, str) for task in level):
                            valid = False
                            break
                    if valid and planning:
                        logger.debug(f"提取到规划: {len(planning)} 个层级")
                        return planning
            except:
                continue
        
        # 2. 尝试JSON解析
        json_match = re.search(r'\{.*"planning".*\[.*\].*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            if "planning" in data:
                planning = data["planning"]
                if isinstance(planning, list):
                    return planning
        
        # 3. 手动解析（更宽松）
        # 查找类似 [xxx, yyy], [zzz] 的模式
        level_pattern = r'\[([^\[\]]+)\]'
        levels = re.findall(level_pattern, response)
        
        if levels:
            planning = []
            for level_str in levels:
                # 分割任务
                tasks = []
                # 尝试用引号分割
                quoted_tasks = re.findall(r'["\']([^"\']+)["\']', level_str)
                if quoted_tasks:
                    tasks = quoted_tasks
                else:
                    # 用逗号分割
                    tasks = [t.strip() for t in level_str.split(',') if t.strip()]
                
                if tasks:
                    planning.append(tasks)
            
            if planning:
                logger.debug(f"手动解析到规划: {len(planning)} 个层级")
                return planning
        
        logger.warning("未能提取到有效的任务规划")
        return None
    
    except Exception as e:
        logger.error(f"提取任务规划失败: {e}")
        return None


def flatten_planning(planning: List[List[str]]) -> List[str]:
    """
    将规划扁平化为任务列表（保持顺序）
    """
    flat = []
    for level in planning:
        flat.extend(level)
    return flat


def find_task_in_planning(task: str, planning: List[List[str]], threshold: float = 0.6, 
                          precomputed_scores: Optional[Dict[Tuple[str, str], float]] = None) -> Optional[Tuple[int, int]]:
    """
    在规划中找到任务的位置
    
    Args:
        task: 待查找的任务
        planning: 规划列表
        threshold: 相似度阈值
        precomputed_scores: 预计算的相似度分数字典 {(task1, task2): score}
    
    Returns:
        (层级索引, 层内索引) 或 None
    """
    best_match = None
    best_score = 0.0
    
    for level_idx, level in enumerate(planning):
        for task_idx, plan_task in enumerate(level):
            # 优先使用预计算的分数
            if precomputed_scores and (task, plan_task) in precomputed_scores:
                score = precomputed_scores[(task, plan_task)]
            else:
                # 降级到规则方法（避免再次调用LLM）
                score = calculate_similarity_rule_based(task, plan_task)
            
            if score > best_score:
                best_score = score
                best_match = (level_idx, task_idx)
    
    if best_score >= threshold:
        return best_match
    return None


def check_dependency_order(
    task1: str,
    task2: str,
    planning: List[List[str]],
    dependencies: Dict[str, List[str]],
    threshold: float = 0.6,
    precomputed_scores: Optional[Dict[Tuple[str, str], float]] = None
) -> bool:
    """
    检查两个任务的依赖顺序是否正确
    
    Args:
        task1: 任务1（应该在前）
        task2: 任务2（应该在后，依赖于task1）
        planning: 模型的规划
        dependencies: 依赖关系字典 {task: [depends_on_tasks]}
        threshold: 相似度阈值
        precomputed_scores: 预计算的相似度分数
    
    Returns:
        顺序是否正确
    """
    pos1 = find_task_in_planning(task1, planning, threshold, precomputed_scores)
    pos2 = find_task_in_planning(task2, planning, threshold, precomputed_scores)
    
    if pos1 is None or pos2 is None:
        return False
    
    level1, _ = pos1
    level2, _ = pos2
    
    # task1应该在task2之前或同级（可并行）
    # 如果task2依赖task1，则task1的level应该 < task2的level
    return level1 <= level2


def validate_task_planning(
    model_response: str,
    ground_truth_tasks: List[str],
    dependencies: Optional[Dict[str, List[str]]] = None,
    ground_truth_planning: Optional[List[List[str]]] = None,
    similarity_threshold: float = 0.6
) -> Dict:
    """
    验证任务规划结果
    
    Args:
        model_response: 模型的响应文本
        ground_truth_tasks: 标准答案的任务列表
        dependencies: 任务依赖关系字典 {task: [depends_on_tasks]}
        ground_truth_planning: 标准答案的规划（可选）
        similarity_threshold: 相似度阈值
    
    Returns:
        评估指标详情字典
        
    详细信息包含:
        - coverage: 集合覆盖度（包含了多少标准任务）
        - order_correctness: 顺序正确性（依赖关系是否正确）
        - level_efficiency: 层级效率（并行度是否合理）
        - matched_tasks: 匹配到的任务
        - missing_tasks: 缺失的任务
        - extra_tasks: 多余的任务
        - dependency_violations: 违反的依赖关系
    """
    logger.info("开始验证任务规划")
    
    # 1. 提取模型的规划
    model_planning = extract_planning_from_response(model_response)
    
    if model_planning is None:
        logger.warning("未能从模型响应中提取到任务规划")
        return {
            "coverage": 0.0,
            "order_correctness": 0.0,
            "level_efficiency": 0.0,
            "overall_score": 0.0,
            "error": "未能提取任务规划",
            "model_planning": None,
            "ground_truth_tasks": ground_truth_tasks
        }
    
    logger.info(f"提取到规划: {len(model_planning)} 个层级")
    for i, level in enumerate(model_planning):
        logger.debug(f"  层级 {i+1}: {level}")
    
    # 2. 计算集合覆盖度 - 使用批量相似度判断优化
    model_tasks_flat = flatten_planning(model_planning)
    matched_gt = set()
    matched_model = set()
    
    # 构建所有需要比较的任务对
    task_pairs = []
    pair_indices = []  # 记录每对任务对应的索引 (gt_idx, model_idx)
    
    for gt_idx, gt_task in enumerate(ground_truth_tasks):
        for model_idx, model_task in enumerate(model_tasks_flat):
            task_pairs.append((gt_task, model_task))
            pair_indices.append((gt_idx, model_idx))
    
    # 批量计算相似度
    if task_pairs:
        try:
            logger.info(f"批量计算 {len(task_pairs)} 对任务的相似度")
            similarities = calculate_similarity_llm_batch(task_pairs)
        except Exception as e:
            logger.warning(f"批量LLM相似度计算失败: {e}，降级到规则方法")
            # 降级到规则方法
            similarities = [
                calculate_similarity_rule_based(t1, t2) 
                for t1, t2 in task_pairs
            ]
    else:
        similarities = []
    
    # 根据相似度进行匹配（贪心算法：优先匹配相似度最高的）
    similarity_scores = list(zip(pair_indices, similarities))
    similarity_scores.sort(key=lambda x: x[1], reverse=True)  # 按相似度降序
    
    for (gt_idx, model_idx), score in similarity_scores:
        gt_task = ground_truth_tasks[gt_idx]
        model_task = model_tasks_flat[model_idx]
        
        # 如果已经匹配过，跳过
        if gt_task in matched_gt or model_task in matched_model:
            continue
        
        # 如果相似度超过阈值，进行匹配
        if score >= similarity_threshold:
            matched_gt.add(gt_task)
            matched_model.add(model_task)
            logger.debug(f"匹配任务: '{gt_task}' <-> '{model_task}' ({score:.2f})")
    
    coverage = len(matched_gt) / len(ground_truth_tasks) if ground_truth_tasks else 0.0
    logger.info(f"集合覆盖度: {coverage:.2%} ({len(matched_gt)}/{len(ground_truth_tasks)})")
    
    # 创建预计算分数字典供依赖检查使用
    precomputed_scores = {}
    for (gt_idx, model_idx), score in zip(pair_indices, similarities):
        gt_task = ground_truth_tasks[gt_idx]
        model_task = model_tasks_flat[model_idx]
        precomputed_scores[(gt_task, model_task)] = score
    
    # 3. 检查顺序正确性（基于依赖关系）
    order_correctness = 1.0
    dependency_violations = []
    
    if dependencies:
        total_dependencies = 0
        correct_dependencies = 0
        
        for task, depends_on in dependencies.items():
            for dep_task in depends_on:
                total_dependencies += 1
                
                # 检查这两个任务的顺序（传递预计算分数）
                is_correct = check_dependency_order(
                    dep_task, task, model_planning, dependencies, 
                    similarity_threshold, precomputed_scores
                )
                
                if is_correct:
                    correct_dependencies += 1
                else:
                    dependency_violations.append({
                        "task": task,
                        "depends_on": dep_task,
                        "description": f"'{task}' 依赖 '{dep_task}'，但顺序不正确"
                    })
                    logger.warning(f"依赖违反: '{task}' 依赖 '{dep_task}'，但顺序不正确")
        
        order_correctness = correct_dependencies / total_dependencies if total_dependencies > 0 else 1.0
        logger.info(f"顺序正确性: {order_correctness:.2%} ({correct_dependencies}/{total_dependencies})")
    
    # 4. 计算层级效率（并行度）
    # 如果提供了标准答案的规划，对比层级数量
    level_efficiency = 1.0
    
    if ground_truth_planning:
        gt_levels = len(ground_truth_planning)
        model_levels = len(model_planning)
        
        # 层级数量应该接近（差异不超过20%）
        level_diff = abs(gt_levels - model_levels) / gt_levels if gt_levels > 0 else 0.0
        level_efficiency = max(0.0, 1.0 - level_diff)
        
        logger.info(f"层级效率: {level_efficiency:.2%} (标准: {gt_levels} 层, 模型: {model_levels} 层)")
    else:
        # 简单启发式：层级不应该太多或太少
        num_tasks = len(model_tasks_flat)
        num_levels = len(model_planning)
        
        if num_levels == num_tasks:
            # 完全串行，效率低
            level_efficiency = 0.5
        elif num_levels == 1:
            # 完全并行，可能不合理
            level_efficiency = 0.7
        else:
            # 有一定并行度，较好
            level_efficiency = 1.0
    
    # 5. 找出缺失和多余的任务
    missing_tasks = [gt for gt in ground_truth_tasks if gt not in matched_gt]
    extra_tasks = [mt for mt in model_tasks_flat if mt not in matched_model]
    
    # 6. 综合评分
    # 权重: coverage 40%, order 40%, efficiency 20%
    overall_score = coverage * 0.4 + order_correctness * 0.4 + level_efficiency * 0.2
    
    # 记录评测结果（不设置通过标准，客观反映指标）
    logger.info(f"评测结果: Coverage={coverage:.2%}, Order={order_correctness:.2%}, "
                f"Efficiency={level_efficiency:.2%}, Overall={overall_score:.2%}")
    
    details = {
        "coverage": coverage,
        "order_correctness": order_correctness,
        "level_efficiency": level_efficiency,
        "overall_score": overall_score,
        "num_matched": len(matched_gt),
        "num_ground_truth": len(ground_truth_tasks),
        "num_model_output": len(model_tasks_flat),
        "num_levels": len(model_planning),
        "matched_tasks": list(matched_gt),
        "missing_tasks": missing_tasks,
        "extra_tasks": extra_tasks,
        "dependency_violations": dependency_violations,
        "model_planning": model_planning,
        "ground_truth_tasks": ground_truth_tasks,
        "ground_truth_planning": ground_truth_planning,
        "similarity_threshold": similarity_threshold
    }
    
    return details


def validate_task_planning_batch(
    test_cases: List[Dict],
    similarity_threshold: float = 0.6
) -> Dict:
    """
    批量验证任务规划
    
    Args:
        test_cases: 测试用例列表，每个用例包含:
            - model_response: 模型响应
            - ground_truth_tasks: 标准任务列表
            - dependencies: 依赖关系（可选）
            - ground_truth_planning: 标准规划（可选）
        similarity_threshold: 相似度阈值
    
    Returns:
        总体统计信息
    """
    results = []
    total_coverage = 0.0
    total_order = 0.0
    total_efficiency = 0.0
    total_overall = 0.0
    
    for i, test_case in enumerate(test_cases):
        logger.info(f"处理测试用例 {i+1}/{len(test_cases)}")
        
        details = validate_task_planning(
            model_response=test_case.get("model_response", ""),
            ground_truth_tasks=test_case.get("ground_truth_tasks", []),
            dependencies=test_case.get("dependencies"),
            ground_truth_planning=test_case.get("ground_truth_planning"),
            similarity_threshold=similarity_threshold
        )
        
        results.append(details)
        total_coverage += details["coverage"]
        total_order += details["order_correctness"]
        total_efficiency += details["level_efficiency"]
        total_overall += details["overall_score"]
    
    num_cases = len(test_cases)
    summary = {
        "total_cases": num_cases,
        "avg_coverage": total_coverage / num_cases if num_cases > 0 else 0.0,
        "avg_order_correctness": total_order / num_cases if num_cases > 0 else 0.0,
        "avg_level_efficiency": total_efficiency / num_cases if num_cases > 0 else 0.0,
        "avg_overall_score": total_overall / num_cases if num_cases > 0 else 0.0,
        "results": results
    }
    
    logger.info(f"批量验证完成: {num_cases} 个案例, "
                f"平均Coverage={summary['avg_coverage']:.2%}, "
                f"平均Order={summary['avg_order_correctness']:.2%}, "
                f"平均Efficiency={summary['avg_level_efficiency']:.2%}, "
                f"平均Overall={summary['avg_overall_score']:.2%}")
    
    return summary


# ============ 辅助函数：生成测试prompt ============

def generate_task_planning_prompt(
    tasks: List[str],
    dependencies: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    生成任务规划的prompt
    
    Args:
        tasks: 任务列表
        dependencies: 依赖关系（用于提示，但不直接告诉模型）
    
    Returns:
        完整的prompt
    """
    prompt = """##任务规划 
目标描述：你将获得一个已经拆解好的子任务列表。请根据各子任务之间的依赖关系、可并行性和优先级，对它们进行分层排序，并以指定的列表-嵌套列表格式返回。

核心规则：
1. **依赖关系**：如果 A 必须在 B 之前完成，则 A 所在的层级必须排在 B 层级之前。
2. **并行执行**：同一层级中的子任务表示可同时（并行）执行；不同层级之间表示必须先后执行。
3. **优先级**：若两个子任务之间没有依赖，但一个更重要或更紧急，请把重要/紧急者放在更靠前的层级；如权重相当，可并行。

输出格式（严格遵守）:
[[子任务1, 子任务3], [子任务2], [子任务4, 子任务5]]

说明：
- 外层列表表示时间/顺序层级
- 内层列表中的元素可并行执行
- 不要输出除列表外的任何额外文字

"""
    
    # 添加任务列表
    prompt += "\n子任务列表：\n"
    for i, task in enumerate(tasks, 1):
        prompt += f"{i}. {task}\n"
    
    # 如果有依赖关系，可以作为提示（但不直接给出答案）
    if dependencies:
        prompt += "\n提示：某些任务之间可能存在依赖关系，请仔细分析任务的逻辑顺序。\n"
    
    return prompt
