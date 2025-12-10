# -*- coding: utf-8 -*-
"""
代码拆分任务验证器

支持两种评估模式：
1. SOTA模型评估（使用LLM判断拆分质量）
2. 结构分析评估（基于函数数量、复杂度、相似度）
"""

import importlib.util
import contextlib
import io
import os
import re
import ast
import inspect
from pathlib import Path
from typing import Any, List, Tuple, Dict, Optional
from difflib import SequenceMatcher


def _load_module_from_file(file_path: str):
    """把任意 .py 文件动态加载为 module 对象"""
    mod_name = os.path.splitext(os.path.basename(file_path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    module = importlib.util.module_from_spec(spec)  
    spec.loader.exec_module(module)               
    return module


def _silent_call(func, *args, **kwargs) -> Any:
    """调用函数时静默 stdout / stderr，返回函数结果"""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        return func(*args, **kwargs)


def _analyze_code_structure(file_path: str) -> Dict:
    """
    分析Python文件的代码结构
    
    返回: {
        'functions': [函数名列表],
        'classes': [类名列表],
        'imports': [导入模块列表],
        'total_lines': 总行数,
        'code_lines': 代码行数（不含空行和注释）,
        'complexity': 复杂度估计
    }
    """
    structure = {
        'functions': [],
        'classes': [],
        'imports': [],
        'total_lines': 0,
        'code_lines': 0,
        'complexity': 0
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        structure['total_lines'] = len(lines)
        
        # 统计代码行数（排除空行和纯注释行）
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                structure['code_lines'] += 1
        
        # 使用AST分析代码结构
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # 统计函数
                if isinstance(node, ast.FunctionDef):
                    structure['functions'].append(node.name)
                    # 复杂度估计：每个函数+1
                    structure['complexity'] += 1
                    # 循环和条件增加复杂度
                    for child in ast.walk(node):
                        if isinstance(child, (ast.For, ast.While, ast.If)):
                            structure['complexity'] += 1
                
                # 统计类
                elif isinstance(node, ast.ClassDef):
                    structure['classes'].append(node.name)
                    structure['complexity'] += 2  # 类的复杂度权重更高
                
                # 统计导入
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        structure['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    structure['imports'].append(node.module or '')
        
        except SyntaxError as e:
            print(f"[warn] AST解析失败: {e}")
            # 回退到正则匹配
            structure['functions'] = re.findall(r'^def\s+(\w+)\s*\(', content, re.MULTILINE)
            structure['classes'] = re.findall(r'^class\s+(\w+)\s*[:\(]', content, re.MULTILINE)
            structure['imports'] = re.findall(r'^(?:import|from)\s+([\w\.]+)', content, re.MULTILINE)
    
    except Exception as e:
        print(f"[error] 分析文件结构失败: {e}")
    
    return structure


def _calculate_code_similarity(file1: str, file2: str) -> float:
    """
    计算两个Python文件的代码相似度（去除空白和注释后）
    
    返回: 0.0-1.0 的相似度
    """
    def normalize_code(file_path: str) -> str:
        """标准化代码：去除注释、空白、统一格式"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 去除注释和空白行
            code_lines = []
            for line in lines:
                # 去除行尾注释
                line = re.sub(r'#.*$', '', line)
                line = line.strip()
                if line:
                    code_lines.append(line)
            
            return '\n'.join(code_lines)
        except Exception as e:
            print(f"[warn] 标准化代码失败: {e}")
            return ""
    
    code1 = normalize_code(file1)
    code2 = normalize_code(file2)
    
    # 使用SequenceMatcher计算相似度
    similarity = SequenceMatcher(None, code1, code2).ratio()
    
    return similarity


def _check_functionality_preserved(file_orig: str, file_split: str, 
                                   function_name: str, mute: bool = True) -> Tuple[bool, str]:
    """
    检查拆分后的代码是否保持了原有功能
    
    返回: (功能是否保持, 说明)
    """
    try:
        mod_orig = _load_module_from_file(file_orig)
        mod_split = _load_module_from_file(file_split)
        
        # 检查目标函数是否存在
        if not hasattr(mod_orig, function_name):
            return False, f"原始文件缺少函数 '{function_name}'"
        if not hasattr(mod_split, function_name):
            return False, f"拆分文件缺少函数 '{function_name}'"
        
        # 执行函数并比较输出
        call = _silent_call if mute else (lambda f, *a, **kw: f(*a, **kw))
        
        try:
            result_orig = call(getattr(mod_orig, function_name))
            result_split = call(getattr(mod_split, function_name))
            
            # 比较结果
            if result_orig == result_split:
                return True, "功能输出一致"
            else:
                return False, f"功能输出不一致: 原始={result_orig}, 拆分={result_split}"
        
        except Exception as e:
            return False, f"函数执行失败: {e}"
    
    except Exception as e:
        return False, f"模块加载失败: {e}"


def _evaluate_split_quality(struct_orig: Dict, struct_split: Dict, 
                            similarity: float) -> Tuple[float, str]:
    """
    评估拆分质量（基于规则）
    
    返回: (评分0-1, 评价说明)
    """
    scores = []
    reasons = []
    
    # 1. 函数数量增加 (30%)
    func_orig = len(struct_orig['functions'])
    func_split = len(struct_split['functions'])
    
    if func_split > func_orig:
        func_score = min(1.0, (func_split - func_orig) / max(func_orig, 1))
        scores.append(func_score * 0.3)
        reasons.append(f"✓ 函数拆分良好 ({func_orig}→{func_split})")
    else:
        scores.append(0.0)
        reasons.append(f"✗ 未进行函数拆分 ({func_orig}→{func_split})")
    
    # 2. 代码行数减少或分布合理 (20%)
    lines_orig = struct_orig['code_lines']
    lines_split = struct_split['code_lines']
    
    if lines_split <= lines_orig:
        line_score = 1.0
        reasons.append(f"✓ 代码简化 ({lines_orig}→{lines_split}行)")
    elif lines_split <= lines_orig * 1.2:  # 允许20%增长（加了注释等）
        line_score = 0.8
        reasons.append(f"△ 代码略有增加 ({lines_orig}→{lines_split}行)")
    else:
        line_score = 0.5
        reasons.append(f"△ 代码明显增加 ({lines_orig}→{lines_split}行)")
    
    scores.append(line_score * 0.2)
    
    # 3. 复杂度降低 (20%)
    complexity_orig = struct_orig['complexity']
    complexity_split = struct_split['complexity']
    
    if complexity_split < complexity_orig:
        complexity_score = 1.0
        reasons.append(f"✓ 复杂度降低 ({complexity_orig}→{complexity_split})")
    elif complexity_split <= complexity_orig * 1.1:
        complexity_score = 0.7
        reasons.append(f"△ 复杂度基本持平 ({complexity_orig}→{complexity_split})")
    else:
        complexity_score = 0.3
        reasons.append(f"△ 复杂度增加 ({complexity_orig}→{complexity_split})")
    
    scores.append(complexity_score * 0.2)
    
    # 4. 保持适度相似（不能完全一样，也不能完全不同）(20%)
    if 0.3 <= similarity <= 0.7:
        similarity_score = 1.0
        reasons.append(f"✓ 重构适度 (相似度{similarity*100:.1f}%)")
    elif 0.2 <= similarity < 0.3 or 0.7 < similarity <= 0.8:
        similarity_score = 0.7
        reasons.append(f"△ 改动较多/较少 (相似度{similarity*100:.1f}%)")
    elif similarity > 0.9:
        similarity_score = 0.2
        reasons.append(f"✗ 几乎未修改 (相似度{similarity*100:.1f}%)")
    else:
        similarity_score = 0.5
        reasons.append(f"△ 改动很大 (相似度{similarity*100:.1f}%)")
    
    scores.append(similarity_score * 0.2)
    
    # 5. 代码质量提升指标 (10%)
    quality_score = 0.0
    
    # 更多的类定义（模块化）
    if len(struct_split['classes']) > len(struct_orig['classes']):
        quality_score += 0.05
        reasons.append("✓ 增加了类定义")
    
    # 导入组织改善
    if len(struct_split['imports']) >= len(struct_orig['imports']):
        quality_score += 0.05
        reasons.append("✓ 导入组织良好")
    
    scores.append(quality_score)
    
    # 计算总分
    total_score = sum(scores)
    reason_text = "\n  ".join(reasons)
    
    return total_score, reason_text


def _evaluate_with_llm(file_orig: str, file_split: str, 
                      judge_client=None) -> Tuple[bool, float, str]:
    """
    使用SOTA模型（LLM）评估代码拆分质量
    
    Args:
        file_orig: 原始文件路径
        file_split: 拆分后文件路径
        judge_client: Judge API客户端（专用评估模型）
    
    返回: (是否通过, 评分0-1, 评价理由)
    """
    if judge_client is None:
        return False, 0.0, "未提供Judge客户端"
    
    try:
        # 读取代码
        with open(file_orig, 'r', encoding='utf-8') as f:
            code_orig = f.read()
        with open(file_split, 'r', encoding='utf-8') as f:
            code_split = f.read()
        
        # 构建评估提示词
        prompt = f"""评估代码重构质量（0-100分，>=70通过）。

原始代码：
{code_orig[:800]}

重构后代码：
{code_split[:800]}

评估标准：功能保持30%、结构改进25%、可读性20%、可维护性15%、最佳实践10%

直接返回JSON（不要其他内容）：
{{
    "score": 85,
    "pass": true,
    "reason": "简短评价（一句话）"
}}
"""
        
        # 调用Judge LLM API
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        response = judge_client.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=200
        )
        
        # 解析响应（处理reasoning_content和content两种情况）
        message = response['choices'][0]['message']
        content = message.get('content') or message.get('reasoning_content', '')
        
        # 提取JSON
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        import json
        result = json.loads(content)
        
        score = result.get('score', 0) / 100.0
        passed = result.get('pass', False) or score >= 0.7
        reason = result.get('reason', 'LLM评估完成')
        
        return passed, score, reason
        
    except Exception as e:
        print(f"[warn] LLM评估失败: {e}")
        return False, 0.0, f"LLM评估出错: {str(e)}"


def validate_split(file_orig: str, file_split: str, function_name: str = None,
                  judge_client=None, use_llm: bool = True, 
                  mute: bool = True) -> Tuple[bool, Dict]:
    """
    验证代码拆分任务
    
    Args:
        file_orig: 原始代码文件路径
        file_split: 拆分后代码文件路径
        function_name: 要测试的函数名（如果提供，会测试功能一致性）
        judge_client: Judge API客户端（专用评估模型，与被测试模型分离）
        use_llm: 是否优先使用LLM评估
        mute: 是否静默函数调用
    
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
    if not os.path.exists(file_orig):
        result['reason'] = f"原始文件不存在: {file_orig}"
        print(f"[错误] {result['reason']}")
        return False, result
    
    if not os.path.exists(file_split):
        result['reason'] = f"拆分文件不存在: {file_split}"
        print(f"[错误] {result['reason']}")
        return False, result
    
    # 分析代码结构
    struct_orig = _analyze_code_structure(file_orig)
    struct_split = _analyze_code_structure(file_split)
    
    result['details']['original'] = struct_orig
    result['details']['split'] = struct_split
    
    # 计算相似度
    similarity = _calculate_code_similarity(file_orig, file_split)
    result['details']['similarity'] = similarity
    
    # 如果提供了函数名，测试功能一致性
    functionality_preserved = True
    if function_name:
        functionality_preserved, func_msg = _check_functionality_preserved(
            file_orig, file_split, function_name, mute
        )
        result['details']['functionality'] = {
            'preserved': functionality_preserved,
            'message': func_msg
        }
        
        if not functionality_preserved:
            result['reason'] = f"功能未保持: {func_msg}"
            print(f"[错误] {result['reason']}")
            return False, result
        else:
            print(f"[信息] ✓ 功能保持一致")
    
    # 选择评估方法
    if use_llm and judge_client is not None and hasattr(judge_client, 'available') and judge_client.available:
        # 方法1: 使用Judge LLM评估
        passed, score, reason = _evaluate_with_llm(file_orig, file_split, judge_client)
        result['method'] = 'llm'
        print(f"[信息] 使用Judge LLM评估")
    else:
        # 方法2: 使用结构分析评估
        score, reason = _evaluate_split_quality(struct_orig, struct_split, similarity)
        passed = score >= 0.6 and functionality_preserved  # 60分及格，且功能保持
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
    
    # 输出结果
    status = "✓ 通过" if passed else "✗ 失败"
    print(f"[结果] {status} | 评分: {score*100:.1f}/100")
    print(f"[详情] {reason}")
    
    return passed, result


# --------- CLI 便捷入口 ---------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python split.py <原始文件> <拆分文件> [函数名]")
        sys.exit(1)
    
    file_a = sys.argv[1]
    file_b = sys.argv[2]
    func_name = sys.argv[3] if len(sys.argv) > 3 else None
    
    passed, details = validate_split(file_a, file_b, func_name, use_llm=False)
    sys.exit(0 if passed else 1)
