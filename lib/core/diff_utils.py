#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diff处理工具模块
统一处理SEARCH/REPLACE格式的代码替换
"""

import re
from typing import List, Tuple


class DiffApplyError(RuntimeError):
    """Diff应用失败异常"""
    pass


# 支持两种SEARCH/REPLACE格式
SEARCH_REPLACE_RE_1 = re.compile(
    r"<<<<<<< SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>> REPLACE",
    re.DOTALL
)

SEARCH_REPLACE_RE_2 = re.compile(
    r"<<<<<<<\s*SEARCH\s*\n(.*?)\n=======\n(.*?)\n>>>>>>>\s*REPLACE",
    re.DOTALL
)


def parse_diff_blocks(diff_text: str) -> List[Tuple[str, str]]:
    """
    从diff文本中解析所有SEARCH/REPLACE块
    
    Args:
        diff_text: 包含SEARCH/REPLACE块的文本
        
    Returns:
        [(search_text, replace_text), ...] 列表
        
    Raises:
        DiffApplyError: 没有找到有效的SEARCH/REPLACE块
    """
    # 尝试第一种格式
    blocks = SEARCH_REPLACE_RE_1.findall(diff_text)
    
    # 如果第一种格式没找到，尝试第二种格式
    if not blocks:
        blocks = SEARCH_REPLACE_RE_2.findall(diff_text)
    
    if not blocks:
        raise DiffApplyError("diff中未检测到合法的SEARCH/REPLACE块")
    
    return blocks


def apply_diff(original: str, diff_text: str) -> str:
    """
    按顺序对原始文本应用diff中的所有SEARCH/REPLACE块
    
    每个块只会替换第一个匹配项。如果某个块找不到匹配，会抛出异常。
    
    Args:
        original: 原始文本
        diff_text: 包含SEARCH/REPLACE块的diff文本
        
    Returns:
        应用diff后的文本
        
    Raises:
        DiffApplyError: SEARCH内容未找到或其他应用错误
    """
    blocks = parse_diff_blocks(diff_text)
    
    result = original
    for idx, (search_text, replace_text) in enumerate(blocks, 1):
        pos = result.find(search_text)
        if pos == -1:
            raise DiffApplyError(
                f"第 {idx} 块的SEARCH内容未找到:\n"
                f"--- SEARCH ---\n{search_text}\n--- END ---"
            )
        # 只替换第一个匹配
        result = result.replace(search_text, replace_text, 1)
    
    return result


def validate_diff(original: str, diff_text: str) -> bool:
    """
    验证diff是否可以成功应用，但不实际修改
    
    Args:
        original: 原始文本
        diff_text: diff文本
        
    Returns:
        True表示可以应用，False表示不能应用
    """
    try:
        apply_diff(original, diff_text)
        return True
    except DiffApplyError:
        return False


if __name__ == "__main__":
    # 测试用例
    original_code = """def hello():
    print("Hello")
    return True
"""
    
    diff = """<<<<<<< SEARCH
def hello():
    print("Hello")
=======
def hello():
    print("Hello, World!")
>>>>>>> REPLACE"""
    
    try:
        result = apply_diff(original_code, diff)
        print("应用diff成功:")
        print(result)
    except DiffApplyError as e:
        print(f"应用diff失败: {e}")
