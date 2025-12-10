#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务分解验证器

评估模型在任务分解阶段的表现：
1. 召回率 (Recall): 标准答案中的任务有多少被模型召回
2. 准确率 (Precision): 模型输出的任务中有多少是正确的

支持两种模式：
- 全集模式: 提供全部候选任务，让模型从中选择
- 开放模式: 不提供候选任务，完全由模型自由分解
"""

import re
import json
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path

from lib.core.logger import get_logger

logger = get_logger(__name__)


def normalize_task(task: str) -> str:
    """
    标准化任务描述
    - 去除多余空格
    - 转小写
    - 去除标点符号
    """
    # 去除多余空格
    task = re.sub(r'\s+', ' ', task.strip())
    # 转小写
    task = task.lower()
    # 去除常见标点
    task = re.sub(r'[，。、；：""''！？《》【】（）,.:;\'\"!?()]', '', task)
    return task


def extract_tasks_from_response(response: str, format_type: str = "auto") -> List[str]:
    """
    从模型响应中提取任务列表
    
    支持格式:
    - JSON: {"goal": "...", "tasks": ["task1", "task2", ...]}
    - Markdown: # 任务要素\n- task1\n- task2
    - XML: <taskDecomposition><tasks><task>task1</task><task>task2</task></tasks></taskDecomposition>
    - 自动检测
    
    Args:
        response: 模型的响应文本
        format_type: 格式类型 - "auto", "json", "markdown", "xml"
    
    Returns:
        提取的任务列表
    """
    tasks = []
    
    if format_type == "auto":
        # 自动检测格式
        response_lower = response.lower()
        if "\"tasks\"" in response and "{" in response:
            format_type = "json"
        elif "<task" in response_lower and "<tasks>" in response_lower:
            format_type = "xml"
        else:
            format_type = "markdown"
        logger.info(f"自动检测格式: {format_type}")
    
    try:
        if format_type == "json":
            # 尝试解析JSON - 支持嵌套和多种格式
            # 1. 先尝试提取完整的JSON对象
            json_match = re.search(r'\{[^{}]*"(?:goal|tasks)"[^{}]*\}', response, re.DOTALL)
            if not json_match:
                # 2. 尝试提取包含嵌套的JSON
                json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # 尝试修复常见的JSON错误
                    json_str = json_str.replace("'", '"')  # 单引号改双引号
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # 移除尾随逗号
                    data = json.loads(json_str)
                
                if "tasks" in data:
                    task_list = data["tasks"]
                    if isinstance(task_list, list):
                        for item in task_list:
                            if isinstance(item, str):
                                tasks.append(item.strip())
                            elif isinstance(item, dict):
                                # 支持多种字段名
                                for key in ["task", "description", "content", "name"]:
                                    if key in item:
                                        tasks.append(str(item[key]).strip())
                                        break
            
            logger.info(f"JSON格式提取到 {len(tasks)} 个任务")
        
        elif format_type == "xml":
            # 提取XML中的task标签 - 支持多种XML结构
            # 1. 提取 <task>纯文本内容</task> （不包含子标签的task）
            # 使用负向前瞻确保匹配的内容中不包含 < 符号（避免匹配到嵌套标签）
            task_pattern = r'<task[^>]*>([^<]+)</task>'
            matches = re.findall(task_pattern, response, re.IGNORECASE)
            for match in matches:
                task_text = match.strip()
                if task_text:
                    tasks.append(task_text)
            
            # 2. 如果上面没找到（可能是多行或有CDATA），使用更复杂的方法
            if not tasks:
                # 匹配可能包含换行的内容
                task_pattern = r'<task[^>]*>(.*?)</task>'
                matches = re.findall(task_pattern, response, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    task_text = match.strip()
                    # 移除内部的CDATA标签
                    task_text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', task_text, flags=re.DOTALL)
                    # 移除内部的其他XML标签
                    task_text = re.sub(r'<[^>]+>', '', task_text)
                    # 移除多余的空白
                    task_text = ' '.join(task_text.split())
                    if task_text and len(task_text) > 3:
                        tasks.append(task_text)
            
            # 3. 如果还是没有找到，尝试提取 <description> 或其他标签
            if not tasks:
                for tag in ['description', 'item', 'subtask', 'step']:
                    pattern = f'<{tag}[^>]*>([^<]+)</{tag}>'
                    matches = re.findall(pattern, response, re.IGNORECASE)
                    for match in matches:
                        task_text = match.strip()
                        if task_text and task_text not in tasks:
                            tasks.append(task_text)
            
            logger.info(f"XML格式提取到 {len(tasks)} 个任务")
        
        else:  # markdown
            # 提取Markdown列表项 - 支持多种列表格式
            lines = response.split('\n')
            in_task_section = False
            
            for line in lines:
                line_stripped = line.strip()
                
                # 检测是否进入任务部分
                if re.match(r'^#+\s*(任务要素|tasks|子任务)', line_stripped, re.IGNORECASE):
                    in_task_section = True
                    continue
                
                # 如果还没进入任务部分，跳过
                if not in_task_section and not tasks:
                    # 但如果已经有任务了，说明可能没有标题
                    pass
                
                # 匹配各种列表格式
                # - task, * task, + task, 1. task, 1) task
                list_match = re.match(r'^([-*+]|\d+[.)])\s+(.+)$', line_stripped)
                if list_match:
                    task_text = list_match.group(2).strip()
                    if task_text and len(task_text) > 2:  # 至少3个字符
                        # 移除可能的Markdown格式
                        task_text = re.sub(r'\*\*(.+?)\*\*', r'\1', task_text)  # 加粗
                        task_text = re.sub(r'`(.+?)`', r'\1', task_text)  # 代码
                        tasks.append(task_text)
                        in_task_section = True  # 找到第一个任务后，认为进入了任务部分
            
            logger.info(f"Markdown格式提取到 {len(tasks)} 个任务")
    
    except Exception as e:
        logger.warning(f"提取任务失败: {e}, 尝试降级处理")
        # 降级处理：按行分割，提取看起来像任务的行
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            # 跳过空行、标题、太短的行
            if not line or line.startswith('#') or len(line) < 5:
                continue
            # 跳过看起来像元数据的行
            if line.startswith('{') or line.startswith('<') or ':' in line[:10]:
                continue
            # 提取列表项
            list_match = re.match(r'^([-*+]|\d+[.)])\s+(.+)$', line)
            if list_match:
                tasks.append(list_match.group(2).strip())
    
    # 去重并保持顺序
    seen = set()
    unique_tasks = []
    for task in tasks:
        if task not in seen:
            seen.add(task)
            unique_tasks.append(task)
    
    if not unique_tasks:
        logger.warning(f"未能从响应中提取到任务列表，响应前200字符:\n{response[:200]}")
    
    return unique_tasks


def calculate_similarity_llm_batch(task_pairs: List[Tuple[str, str]]) -> List[float]:
    """
    使用 LLM Judge 批量计算多对任务描述的语义相似度
    
    Args:
        task_pairs: 任务对列表 [(task1_a, task2_a), (task1_b, task2_b), ...]
        
    Returns:
        相似度分数列表
    """
    from lib.api.judge_client import get_judge_client
    
    if not task_pairs:
        return []
    
    # 构建批量判断的提示词 - 一次性处理所有任务对
    prompt = "请判断以下每对任务描述的语义相似度。\n\n判断规则:\n"
    prompt += "1. 如果两个任务的核心目标完全一致，即使表述不同，也视为高度相似 (0.8-1.0)\n"
    prompt += "2. 如果任务A是任务B的具体化或细化（或反之），视为高度相似 (0.7-0.9)\n"
    prompt += "3. 如果任务A包含任务B的全部内容并有额外内容，视为部分相似 (0.5-0.7)\n"
    prompt += "4. 如果两个任务的目标部分重叠，视为部分相似 (0.3-0.5)\n"
    prompt += "5. 如果两个任务的目标完全不同，视为不相似 (0.0-0.3)\n\n"
    
    # 添加所有任务对
    for i, (task1, task2) in enumerate(task_pairs, 1):
        prompt += f"【任务对 {i}】\n"
        prompt += f"A: {task1}\n"
        prompt += f"B: {task2}\n\n"
    
    prompt += f"请为每对任务输出一个相似度分数(0.0-1.0)。\n"
    prompt += f"严格按照以下格式输出 {len(task_pairs)} 行，每行一个分数：\n"
    prompt += "1: 0.85\n"
    prompt += "2: 0.60\n"
    prompt += "3: 0.20\n"
    prompt += "...\n"
    prompt += f"\n注意：必须输出全部 {len(task_pairs)} 个分数，不要遗漏任何一个。"
    
    try:
        judge_client = get_judge_client()
        
        logger.info(f"一次性批量判断 {len(task_pairs)} 对任务的相似度")
        
        response = judge_client.chat_completion(
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response['choices'][0]['message']['content'].strip()
        
        logger.info(f"LLM 批量判断响应:\n{content}")
        
        # 解析每一行
        import re
        scores = []
        parsed_indices = []
        
        for line in content.split('\n'):
            line = line.strip()
            # 匹配 "数字: 分数" 格式
            match = re.match(r'(\d+):\s*(\d+\.?\d*)', line)
            if match:
                idx = int(match.group(1))
                score = float(match.group(2))
                # 确保在 0-1 范围内
                if score > 1.0:
                    score = score / 100.0
                score = max(0.0, min(1.0, score))
                parsed_indices.append(idx)
                scores.append((idx, score))
        
        logger.info(f"解析出 {len(scores)} 个分数，期望 {len(task_pairs)} 个")
        
        # 按照索引排序，确保顺序正确
        scores.sort(key=lambda x: x[0])
        result = [score for idx, score in scores]
        
        # 检查是否有缺失的索引
        expected_indices = set(range(1, len(task_pairs) + 1))
        parsed_indices_set = set(parsed_indices)
        missing_indices = expected_indices - parsed_indices_set
        
        if missing_indices:
            logger.warning(f"LLM 批量判断缺少以下索引的分数: {sorted(missing_indices)}")
            # 为缺失的索引补充默认分数（使用规则方法）
            for missing_idx in sorted(missing_indices):
                pair = task_pairs[missing_idx - 1]
                fallback_score = calculate_similarity_rule_based(pair[0], pair[1])
                result.insert(missing_idx - 1, fallback_score)
                logger.warning(f"为任务对 {missing_idx} 使用规则方法补充分数: {fallback_score:.2f}")
        
        if len(result) != len(task_pairs):
            logger.error(f"最终分数数量({len(result)})与任务对数量({len(task_pairs)})不匹配，降级到规则方法")
            return [calculate_similarity_rule_based(t1, t2) for t1, t2 in task_pairs]
        
        return result
        
    except Exception as e:
        logger.warning(f"LLM 批量相似度判断失败: {e}，降级到规则方法")
        # 降级到逐个规则判断
        return [calculate_similarity_rule_based(t1, t2) for t1, t2 in task_pairs]


def calculate_similarity_llm(task1: str, task2: str) -> float:
    """
    使用 LLM Judge 计算两个任务描述的语义相似度
    
    Args:
        task1: 第一个任务描述
        task2: 第二个任务描述
        
    Returns:
        相似度分数 (0.0 - 1.0)
        - 1.0: 语义完全相同或等价
        - 0.7-0.9: 语义高度相似
        - 0.4-0.6: 语义部分相似
        - 0.0-0.3: 语义不同
    """
    from lib.api.judge_client import get_judge_client
    
    prompt = f"""请判断以下两个任务描述是否表达了相同或相似的意图。

任务A: {task1}
任务B: {task2}

判断规则:
1. 如果两个任务的核心目标完全一致，即使表述不同，也视为高度相似
2. 如果任务A是任务B的具体化或细化（或反之），视为高度相似
3. 如果任务A包含任务B的全部内容并有额外内容，视为部分相似
4. 如果两个任务的目标完全不同，视为不相似

请直接输出一个0.0到1.0之间的相似度分数，不要有其他解释。
格式: 仅输出数字，例如: 0.85"""

    try:
        judge_client = get_judge_client()
        response = judge_client.chat_completion(
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 提取分数
        content = response['choices'][0]['message']['content'].strip()
        
        # 尝试提取数字
        import re
        match = re.search(r'(\d+\.?\d*)', content)
        if match:
            score = float(match.group(1))
            # 确保在 0-1 范围内
            if score > 1.0:
                score = score / 100.0  # 可能是百分比
            score = max(0.0, min(1.0, score))
            return score
        else:
            logger.warning(f"无法从 LLM 响应中提取分数: {content}")
            # 降级到基于规则的方法
            return calculate_similarity_rule_based(task1, task2)
            
    except Exception as e:
        logger.warning(f"LLM 相似度判断失败: {e}，降级到规则方法")
        return calculate_similarity_rule_based(task1, task2)


def calculate_similarity_rule_based(task1: str, task2: str) -> float:
    """
    使用基于规则的方法计算两个任务描述的相似度
    
    使用编辑距离 + 关键词匹配（作为 LLM 的 fallback）
    """
    from difflib import SequenceMatcher
    
    # 标准化
    t1 = normalize_task(task1)
    t2 = normalize_task(task2)
    
    # 完全匹配
    if t1 == t2:
        return 1.0
    
    # 序列匹配
    seq_sim = SequenceMatcher(None, t1, t2).ratio()
    
    # 关键词匹配（分词后计算交集/并集）
    words1 = set(t1.split())
    words2 = set(t2.split())
    
    if not words1 or not words2:
        return seq_sim
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    keyword_sim = intersection / union if union > 0 else 0
    
    # 综合相似度（权重：序列60% + 关键词40%）
    return seq_sim * 0.6 + keyword_sim * 0.4


def calculate_similarity(task1: str, task2: str, use_llm: bool = True) -> float:
    """
    计算两个任务描述的相似度
    
    Args:
        task1: 第一个任务描述
        task2: 第二个任务描述
        use_llm: 是否使用 LLM 判断（默认 True）
        
    Returns:
        相似度分数 (0.0 - 1.0)
    """
    if use_llm:
        return calculate_similarity_llm(task1, task2)
    else:
        return calculate_similarity_rule_based(task1, task2)


def find_best_match(task: str, candidates: List[str], threshold: float = 0.6) -> Optional[str]:
    """
    在候选任务列表中找到最佳匹配
    
    Args:
        task: 待匹配的任务
        candidates: 候选任务列表
        threshold: 相似度阈值（默认0.6）
    
    Returns:
        最佳匹配的任务，如果没有超过阈值则返回None
    """
    best_match = None
    best_score = 0.0
    
    for candidate in candidates:
        score = calculate_similarity(task, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate
    
    if best_score >= threshold:
        return best_match
    return None


def validate_task_decomposition(
    model_response: str,
    ground_truth: List[str],
    mode: str = "open",
    format_type: str = "auto",
    similarity_threshold: float = 0.6,
    use_llm_similarity: bool = True
) -> Dict:
    """
    验证任务分解结果
    
    Args:
        model_response: 模型的响应文本
        ground_truth: 标准答案的任务列表
        mode: 模式 - "open"(开放) 或 "constrained"(全集)
        format_type: 输出格式类型
        similarity_threshold: 相似度阈值
        use_llm_similarity: 是否使用 LLM 判断语义相似度（默认 True）
    
    Returns:
        (评估指标详情字典,)
        
    详细信息包含:
        - recall: 召回率
        - precision: 准确率
        - f1_score: F1分数
        - matched_tasks: 匹配到的任务对
        - missed_tasks: 未召回的任务
        - extra_tasks: 多余的任务
        - model_tasks: 模型输出的任务列表
    """
    logger.info(f"开始验证任务分解: mode={mode}, format={format_type}, use_llm={use_llm_similarity}")
    
    # 1. 提取模型输出的任务
    model_tasks = extract_tasks_from_response(model_response, format_type)
    
    if not model_tasks:
        logger.warning("未能从模型响应中提取到任务列表")
        return {
            "recall": 0.0,
            "precision": 0.0,
            "f1_score": 0.0,
            "error": "未能提取任务列表",
            "model_tasks": [],
            "ground_truth": ground_truth
        }
    
    logger.info(f"提取到 {len(model_tasks)} 个任务")
    
    # 2. 匹配任务
    matched_pairs = []  # (model_task, ground_truth_task, similarity)
    matched_gt = set()  # 已匹配的标准答案任务
    matched_model = set()  # 已匹配的模型任务
    
    if use_llm_similarity:
        # 使用批量 LLM 判断
        logger.info("使用批量 LLM 语义相似度判断")
        
        # 生成所有需要判断的任务对
        all_pairs = []
        pair_indices = []  # 记录每个 pair 对应的 (model_idx, gt_idx)
        
        for model_idx, model_task in enumerate(model_tasks):
            for gt_idx, gt_task in enumerate(ground_truth):
                all_pairs.append((model_task, gt_task))
                pair_indices.append((model_idx, gt_idx))
        
        # 批量计算相似度
        logger.info(f"需要判断 {len(all_pairs)} 对任务的相似度")
        similarities = calculate_similarity_llm_batch(all_pairs)
        
        # 构建相似度矩阵
        similarity_matrix = {}
        for (model_idx, gt_idx), sim in zip(pair_indices, similarities):
            similarity_matrix[(model_idx, gt_idx)] = sim
        
        # 使用贪心算法进行匹配：优先匹配相似度最高的
        remaining_model = set(range(len(model_tasks)))
        remaining_gt = set(range(len(ground_truth)))
        
        while remaining_model and remaining_gt:
            # 找到当前最高相似度的配对
            best_sim = 0.0
            best_pair = None
            
            for m_idx in remaining_model:
                for gt_idx in remaining_gt:
                    sim = similarity_matrix.get((m_idx, gt_idx), 0.0)
                    if sim > best_sim:
                        best_sim = sim
                        best_pair = (m_idx, gt_idx)
            
            # 如果最佳相似度低于阈值，停止匹配
            if best_sim < similarity_threshold:
                break
            
            if best_pair:
                m_idx, gt_idx = best_pair
                model_task = model_tasks[m_idx]
                gt_task = ground_truth[gt_idx]
                
                matched_pairs.append((model_task, gt_task, best_sim))
                matched_gt.add(gt_task)
                matched_model.add(model_task)
                remaining_model.remove(m_idx)
                remaining_gt.remove(gt_idx)
                
                logger.info(f"✓ 匹配: '{model_task[:50]}...' <-> '{gt_task[:50]}...' (相似度: {best_sim:.2f})")
    else:
        # 使用逐个规则判断（原有逻辑）
        logger.info("使用规则方法计算相似度")
        
        for model_task in model_tasks:
            # 在标准答案中找最佳匹配
            available_gt = [gt for gt in ground_truth if gt not in matched_gt]
            best_match = None
            best_score = 0.0
            
            for gt_task in available_gt:
                score = calculate_similarity_rule_based(model_task, gt_task)
                if score > best_score:
                    best_score = score
                    best_match = gt_task
            
            if best_match and best_score >= similarity_threshold:
                matched_pairs.append((model_task, best_match, best_score))
                matched_gt.add(best_match)
                matched_model.add(model_task)
                logger.info(f"✓ 匹配: '{model_task[:50]}...' <-> '{best_match[:50]}...' (相似度: {best_score:.2f})")
            else:
                logger.debug(f"✗ 未匹配: '{model_task[:50]}...' (最高相似度: {best_score:.2f})")
    
    # 3. 计算指标
    num_matched = len(matched_pairs)
    num_ground_truth = len(ground_truth)
    num_model_output = len(model_tasks)
    
    recall = num_matched / num_ground_truth if num_ground_truth > 0 else 0.0
    precision = num_matched / num_model_output if num_model_output > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # 4. 找出未召回和多余的任务
    missed_tasks = [gt for gt in ground_truth if gt not in matched_gt]
    extra_tasks = [mt for mt in model_tasks if mt not in matched_model]
    
    # 5. 记录评测结果（不设置通过标准，客观反映指标）
    logger.info(f"评测结果: Recall={recall:.2%}, Precision={precision:.2%}, F1={f1_score:.2%}")
    
    details = {
        "recall": recall,
        "precision": precision,
        "f1_score": f1_score,
        "num_matched": num_matched,
        "num_ground_truth": num_ground_truth,
        "num_model_output": num_model_output,
        "matched_pairs": [(m, g, s) for m, g, s in matched_pairs],
        "missed_tasks": missed_tasks,
        "extra_tasks": extra_tasks,
        "model_tasks": model_tasks,
        "ground_truth": ground_truth,
        "mode": mode,
        "similarity_threshold": similarity_threshold
    }
    
    return details


def validate_task_decomposition_batch(
    test_cases: List[Dict],
    similarity_threshold: float = 0.6
) -> Dict:
    """
    批量验证任务分解
    
    Args:
        test_cases: 测试用例列表，每个用例包含:
            - model_response: 模型响应
            - ground_truth: 标准答案
            - mode: 模式
            - format_type: 格式类型
        similarity_threshold: 相似度阈值
    
    Returns:
        总体统计信息
    """
    results = []
    total_recall = 0.0
    total_precision = 0.0
    total_f1 = 0.0
    
    for i, test_case in enumerate(test_cases):
        logger.info(f"处理测试用例 {i+1}/{len(test_cases)}")
        
        details = validate_task_decomposition(
            model_response=test_case.get("model_response", ""),
            ground_truth=test_case.get("ground_truth", []),
            mode=test_case.get("mode", "open"),
            format_type=test_case.get("format_type", "auto"),
            similarity_threshold=similarity_threshold
        )
        
        results.append(details)
        total_recall += details["recall"]
        total_precision += details["precision"]
        total_f1 += details["f1_score"]
    
    num_cases = len(test_cases)
    summary = {
        "total_cases": num_cases,
        "avg_recall": total_recall / num_cases if num_cases > 0 else 0.0,
        "avg_precision": total_precision / num_cases if num_cases > 0 else 0.0,
        "avg_f1_score": total_f1 / num_cases if num_cases > 0 else 0.0,
        "results": results
    }
    
    logger.info(f"批量验证完成: {num_cases} 个案例, "
                f"平均Recall={summary['avg_recall']:.2%}, "
                f"平均Precision={summary['avg_precision']:.2%}, "
                f"平均F1={summary['avg_f1_score']:.2%}")
    
    return summary


# ============ 辅助函数：生成测试prompt ============

def generate_task_decomposition_prompt(
    question: str,
    mode: str = "open",
    all_tasks: Optional[List[str]] = None,
    format_type: str = "json"
) -> str:
    """
    生成任务分解的prompt
    
    Args:
        question: 用户问题
        mode: "open" 或 "constrained"
        all_tasks: 全集模式下的候选任务列表
        format_type: 输出格式
    
    Returns:
        完整的prompt
    """
    # 基础prompt
    if mode == "constrained" and all_tasks:
        # 全集模式
        base_prompt = """##任务分解 目标描述:
在进行任务分解时，严格要求从以下提供的子任务集合中选择3-5个子任务，作为最终的任务分解结果。所选子任务必须与集合中的元素完全相同，不允许任何修改或重新措辞。确保所选子任务能够有效地支持和实现用户的终极目标。

子任务集合如下：
"""
        for task in all_tasks:
            base_prompt += f"- {task}\n"
    else:
        # 开放模式
        base_prompt = """##任务分解 目标描述：
在回答问题前，识别用户的终极目标（goal）。将该目标原子化拆分为3-5个独立的子任务（task），这些子任务应是问题或课题本身，而非具体的执行步骤或操作指令。

子任务要求：
• 每个子任务需配有一个动宾短语形式的标签（tag），tag的长度要严格限制在4-5个字。可用动词包括但不限于：设计，开发，优化，验证，管理等。

示例：
task：设计低功耗电路
tag：设计电路
"""
    
    # 格式要求
    format_prompts = {
        "json": '{ "goal": "{goal}", "tasks": [ "task1", "task2", "task3" ] }',
        "markdown": "# 目标\n{goal}\n\n# 任务要素\n- task1\n- task2\n- task3",
        "xml": "<taskDecomposition>\n  <goal>{goal}</goal>\n  <tasks>\n    <task>task1</task>\n    <task>task2</task>\n  </tasks>\n</taskDecomposition>"
    }
    
    format_prompt = f"\n输出格式要求：\n{format_prompts.get(format_type, format_prompts['json'])}\n"
    
    # 用户问题
    question_prompt = f"\n用户问题：{question}\n"
    
    return base_prompt + format_prompt + question_prompt
