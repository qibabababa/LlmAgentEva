# -*- coding: utf-8 -*-
"""
代码总结任务验证器

支持两种评估模式：
1. SOTA模型评估（使用LLM判断总结质量）
2. 规则评估（基于格式、关键词、相似度）
"""

import os
import re
from pathlib import Path
from typing import Tuple, Dict, Optional
from difflib import SequenceMatcher


# -------------------------- 格式检查 -------------------------- #
def _check_format(content: str) -> Tuple[bool, str]:
    """
    检查 README.md 是否满足格式约定：
      1. 以 ### 或 # 开头
      2. 必须含有关键段落标题
      3. 内容不能太短（至少500字符）
      4. 如果有mermaid代码块，需要正确闭合
    返回 (是否通过, 失败原因)
    """
    content = content.strip()
    
    # 检查1: 内容长度
    if len(content) < 500:
        return False, f"README 内容过短 ({len(content)} 字符 < 500)"
    
    # 检查2: 必须以标题开头
    if not (content.startswith("#") or content.startswith("###")):
        return False, "README 未以标题开头 (# 或 ###)"
    
    # 检查3: 必须包含关键段落（灵活匹配）
    required_keywords = [
        ["整体说明", "项目说明", "概述", "简介"],
        ["依赖", "依赖关系", "模块关系", "架构"],
        ["数据流", "工作流", "流程", "执行流程"],
        ["改进", "建议", "优化", "TODO"]
    ]
    
    missing_sections = []
    for keywords in required_keywords:
        found = any(kw in content for kw in keywords)
        if not found:
            missing_sections.append(keywords[0])
    
    if missing_sections:
        return False, f"缺少段落: {', '.join(missing_sections)}"
    
    # 检查4: mermaid 代码块闭合（如果有的话）
    if "```mermaid" in content:
        mermaid_open = content.count("```mermaid")
        # 计算独立的闭合标记（排除mermaid后的```）
        lines = content.split('\n')
        close_count = 0
        for line in lines:
            stripped = line.strip()
            if stripped == "```" or (stripped.startswith("```") and not stripped.startswith("```mermaid")):
                close_count += 1
        
        if mermaid_open > close_count:
            return False, f"mermaid 代码块未正确闭合 (开: {mermaid_open}, 闭: {close_count})"
    
    # 检查5: 至少包含3个段落标题
    title_count = len(re.findall(r'^#{1,6}\s+.+', content, re.MULTILINE))
    if title_count < 3:
        return False, f"段落标题过少 ({title_count} < 3)"
    
    return True, ""


def _extract_code_structure(src_dir: Path) -> Dict[str, any]:
    """
    分析源代码目录，提取结构信息
    返回: {
        'files': [文件列表],
        'functions': [函数列表],
        'classes': [类列表],
        'imports': [导入模块列表]
    }
    """
    structure = {
        'files': [],
        'functions': set(),
        'classes': set(),
        'imports': set()
    }
    
    if not src_dir.exists():
        return structure
    
    # 遍历Python文件
    for py_file in src_dir.rglob("*.py"):
        structure['files'].append(py_file.name)
        
        try:
            content = py_file.read_text(encoding='utf-8')
            
            # 提取函数定义
            functions = re.findall(r'^def\s+(\w+)\s*\(', content, re.MULTILINE)
            structure['functions'].update(functions)
            
            # 提取类定义
            classes = re.findall(r'^class\s+(\w+)\s*[:\(]', content, re.MULTILINE)
            structure['classes'].update(classes)
            
            # 提取import语句
            imports = re.findall(r'^import\s+([\w\.]+)', content, re.MULTILINE)
            from_imports = re.findall(r'^from\s+([\w\.]+)\s+import', content, re.MULTILINE)
            structure['imports'].update(imports)
            structure['imports'].update(from_imports)
            
        except Exception as e:
            print(f"[warn] 无法解析文件 {py_file}: {e}")
    
    return structure


def _check_coverage(readme_content: str, code_structure: Dict) -> Tuple[float, str]:
    """
    检查README是否覆盖了代码的关键信息
    返回: (覆盖率, 缺失信息说明)
    """
    coverage_scores = []
    missing_info = []
    
    readme_lower = readme_content.lower()
    
    # 1. 文件提及率
    if code_structure['files']:
        mentioned_files = sum(1 for f in code_structure['files'] 
                             if f.lower().replace('.py', '') in readme_lower)
        file_coverage = mentioned_files / len(code_structure['files'])
        coverage_scores.append(file_coverage)
        if file_coverage < 0.5:
            missing_info.append(f"文件覆盖率低 ({mentioned_files}/{len(code_structure['files'])})")
    
    # 2. 关键函数/类提及
    key_names = list(code_structure['functions']) + list(code_structure['classes'])
    if key_names:
        mentioned_names = sum(1 for name in key_names if name.lower() in readme_lower)
        name_coverage = mentioned_names / len(key_names)
        coverage_scores.append(name_coverage * 0.5)  # 权重0.5，因为不需要全部提及
    
    # 3. 依赖库提及
    if code_structure['imports']:
        mentioned_imports = sum(1 for imp in code_structure['imports'] 
                               if imp.lower() in readme_lower)
        import_coverage = mentioned_imports / len(code_structure['imports'])
        coverage_scores.append(import_coverage * 0.5)  # 权重0.5
    
    # 计算总覆盖率
    total_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    
    return total_coverage, "; ".join(missing_info) if missing_info else "覆盖良好"


def _evaluate_with_llm(readme_content: str, code_structure: Dict, 
                       judge_client=None) -> Tuple[bool, float, str]:
    """
    使用SOTA模型（LLM）评估README质量
    
    Args:
        readme_content: README内容
        code_structure: 代码结构信息
        judge_client: Judge API客户端（专用评估模型）
    
    返回: (是否通过, 评分0-1, 评价理由)
    """
    if judge_client is None:
        return False, 0.0, "未提供Judge客户端"
    
    # 构建评估提示词
    files_str = ', '.join(code_structure['files'][:5])
    functions_str = ', '.join(list(code_structure['functions'])[:5])
    
    prompt = f"""评估以下README文档质量（0-100分，>=70通过）。

代码信息：{len(code_structure['files'])}个文件（{files_str}），{len(code_structure['functions'])}个函数

README内容：
{readme_content[:800]}

评估标准：完整性30%、准确性30%、清晰度20%、实用性20%

直接返回JSON（不要其他内容）：
{{
    "score": 85,
    "pass": true,
    "reason": "简短评价（一句话）"
}}
"""
    
    try:
        # 调用Judge LLM API
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        response = judge_client.chat_completion(
            messages=messages,
            temperature=0.1,  # 极低温度，确保稳定输出
            max_tokens=200
        )
        
        # 解析响应（处理reasoning_content和content两种情况）
        message = response['choices'][0]['message']
        content = message.get('content') or message.get('reasoning_content', '')
        
        # 提取JSON（可能包裹在```json```中）
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        import json
        result = json.loads(content)
        
        score = result.get('score', 0) / 100.0  # 转换为0-1
        passed = result.get('pass', False) or score >= 0.7
        reason = result.get('reason', 'LLM评估完成')
        
        return passed, score, reason
        
    except Exception as e:
        print(f"[warn] LLM评估失败: {e}")
        return False, 0.0, f"LLM评估出错: {str(e)}"


def _evaluate_with_rules(readme_content: str, code_structure: Dict) -> Tuple[bool, float, str]:
    """
    使用规则和相似度评估README质量（备用方案）
    
    返回: (是否通过, 评分0-1, 评价理由)
    """
    scores = []
    reasons = []
    
    # 1. 格式检查 (20%)
    format_ok, format_reason = _check_format(readme_content)
    if format_ok:
        scores.append(0.2)
        reasons.append("✓ 格式正确")
    else:
        scores.append(0.0)
        reasons.append(f"✗ 格式: {format_reason}")
    
    # 2. 内容覆盖率 (40%)
    coverage, coverage_info = _check_coverage(readme_content, code_structure)
    scores.append(coverage * 0.4)
    reasons.append(f"{'✓' if coverage >= 0.5 else '✗'} 覆盖率: {coverage*100:.1f}% ({coverage_info})")
    
    # 3. 内容质量 (40%)
    content_score = 0.0
    
    # 3.1 长度适中 (10%)
    length = len(readme_content)
    if 1000 <= length <= 5000:
        content_score += 0.1
        reasons.append(f"✓ 长度适中 ({length} 字符)")
    elif length > 5000:
        content_score += 0.08
        reasons.append(f"△ 稍长 ({length} 字符)")
    else:
        content_score += 0.05
        reasons.append(f"△ 稍短 ({length} 字符)")
    
    # 3.2 有代码示例或图表 (10%)
    has_code_block = '```' in readme_content
    has_mermaid = '```mermaid' in readme_content
    if has_code_block or has_mermaid:
        content_score += 0.1
        reasons.append("✓ 包含代码块或图表")
    
    # 3.3 结构清晰（多个段落）(10%)
    sections = len(re.findall(r'^#{1,6}\s+.+', readme_content, re.MULTILINE))
    if sections >= 5:
        content_score += 0.1
        reasons.append(f"✓ 结构清晰 ({sections}个段落)")
    elif sections >= 3:
        content_score += 0.07
        reasons.append(f"△ 结构基本清晰 ({sections}个段落)")
    
    # 3.4 包含关键信息 (10%)
    key_info_count = 0
    key_infos = ['功能', '使用', '依赖', '安装', '配置', '示例', 'API', '架构']
    for info in key_infos:
        if info in readme_content:
            key_info_count += 1
    
    if key_info_count >= 4:
        content_score += 0.1
        reasons.append(f"✓ 包含关键信息 ({key_info_count}/{len(key_infos)})")
    else:
        content_score += 0.05
        reasons.append(f"△ 关键信息不足 ({key_info_count}/{len(key_infos)})")
    
    scores.append(content_score)
    
    # 计算总分
    total_score = sum(scores)
    passed = total_score >= 0.6  # 60分及格
    
    reason_text = "\n  ".join(reasons)
    
    return passed, total_score, reason_text


def validate_sum(md_file: Path, src_dir: Optional[Path] = None, 
                 judge_client=None, use_llm: bool = True) -> Tuple[bool, Dict]:
    """
    验证代码总结任务
    
    Args:
        md_file: 生成的README.md文件路径
        src_dir: 源代码目录路径（用于提取代码结构）
        judge_client: Judge API客户端（专用评估模型，与被测试模型分离）
        use_llm: 是否优先使用LLM评估
    
    Returns:
        (是否通过, 详细信息字典)
    """
    result = {
        'pass': False,
        'score': 0.0,
        'method': 'none',
        'reason': '',
        'details': {}
    }
    
    # 检查文件存在性
    if not md_file.exists():
        result['reason'] = f"README 不存在: {md_file}"
        print(f"[错误] {result['reason']}")
        return False, result
    
    # 读取README内容
    try:
        readme_content = md_file.read_text(encoding="utf-8")
    except Exception as e:
        result['reason'] = f"无法读取README: {e}"
        print(f"[错误] {result['reason']}")
        return False, result
    
    # 提取代码结构
    code_structure = {'files': [], 'functions': set(), 'classes': set(), 'imports': set()}
    if src_dir and src_dir.exists():
        code_structure = _extract_code_structure(src_dir)
        result['details']['code_structure'] = {
            'files': len(code_structure['files']),
            'functions': len(code_structure['functions']),
            'classes': len(code_structure['classes']),
            'imports': len(code_structure['imports'])
        }
    
    # 选择评估方法
    if use_llm and judge_client is not None and hasattr(judge_client, 'available') and judge_client.available:
        # 方法1: 使用Judge LLM评估
        passed, score, reason = _evaluate_with_llm(readme_content, code_structure, judge_client)
        result['method'] = 'llm'
        print(f"[信息] 使用Judge LLM评估")
    else:
        # 方法2: 使用规则评估
        passed, score, reason = _evaluate_with_rules(readme_content, code_structure)
        result['method'] = 'rules'
        if judge_client is None or not hasattr(judge_client, 'available'):
            print(f"[信息] 使用规则评估（未提供Judge客户端）")
        elif not judge_client.available:
            print(f"[信息] 使用规则评估（Judge不可用）")
        else:
            print(f"[信息] 使用规则评估（LLM评估被禁用）")
    
    result['pass'] = passed
    result['score'] = score
    result['reason'] = reason
    result['details']['readme_length'] = len(readme_content)
    
    # 输出结果
    status = "✓ 通过" if passed else "✗ 失败"
    print(f"[结果] {status} | 评分: {score*100:.1f}/100")
    print(f"[详情] {reason}")
    
    return passed, result
