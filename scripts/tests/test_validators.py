#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新的验证器功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.validators.summary import validate_sum
from lib.validators.split import validate_split
from lib.api.client import APIClient


def test_sum_validator():
    """测试代码总结验证器"""
    print("=" * 60)
    print("测试代码总结验证器 (sum)")
    print("=" * 60)
    
    # 准备测试数据
    project_root = Path(__file__).parent.parent
    md_file = project_root / "data/tasks/code_sum/sample_scraper_1/README.md"
    src_dir = project_root / "data/tasks/code_sum/sample_scraper_1/src"
    
    # 创建一个测试README文件
    if not md_file.exists():
        md_file.parent.mkdir(parents=True, exist_ok=True)
        test_content = """### 项目说明

这是一个网页数据抓取工具。

### 整体说明:
本项目实现了一个简单但功能完整的网页抓取管道。

### 依赖图 (mermaid):
```mermaid
graph LR
    A[config.py] --> B[fetcher.py]
    B --> C[parser.py]
    C --> D[pipeline.py]
```

### 数据流:
1. 配置加载（config.py）
2. 数据抓取（fetcher.py）
3. 数据解析（parser.py）
4. 数据处理（pipeline.py）

### 改进建议:
- 添加错误重试机制
- 支持异步抓取
- 增加数据缓存
"""
        md_file.write_text(test_content, encoding='utf-8')
        print(f"✓ 创建测试README文件: {md_file}")
    
    # 测试1: 规则评估（不使用LLM）
    print("\n--- 测试1: 规则评估 ---")
    passed, details = validate_sum(
        md_file=md_file,
        src_dir=src_dir if src_dir.exists() else None,
        api_client=None,
        use_llm=False
    )
    
    print(f"\n结果: {'✓ 通过' if passed else '✗ 失败'}")
    print(f"评分: {details['score']*100:.1f}/100")
    print(f"方法: {details['method']}")
    print(f"原因:\n  {details['reason']}")
    
    # 测试2: LLM评估（如果有API）
    print("\n--- 测试2: LLM评估 ---")
    try:
        client = APIClient()
        passed_llm, details_llm = validate_sum(
            md_file=md_file,
            src_dir=src_dir if src_dir.exists() else None,
            api_client=client,
            use_llm=True
        )
        
        print(f"\n结果: {'✓ 通过' if passed_llm else '✗ 失败'}")
        print(f"评分: {details_llm['score']*100:.1f}/100")
        print(f"方法: {details_llm['method']}")
        print(f"原因: {details_llm['reason']}")
    except Exception as e:
        print(f"⚠️ LLM评估跳过: {e}")
    
    return passed


def test_split_validator():
    """测试代码拆分验证器"""
    print("\n" + "=" * 60)
    print("测试代码拆分验证器 (split)")
    print("=" * 60)
    
    # 准备测试数据
    project_root = Path(__file__).parent.parent
    orig_file = project_root / "data/tasks/code_split/case_1.py"
    
    # 创建一个简化版的拆分文件用于测试
    split_file = project_root / "data/tasks/code_split/fix_1.py"
    
    if not split_file.exists():
        test_content = """import statistics, datetime

def load_data(fillna: str = '0'):
    \"\"\"加载和清洗数据\"\"\"
    header = ['id', 'num_height', 'num_weight', 'city']
    rows = [
        ['1', '170', '60', 'Shanghai'],
        ['2', '180', '',   'Beijing'],
        ['3', '',   '55',  'Guangzhou'],
        ['',  '',   '',    ''],          
        ['4', '175', '70', 'Shenzhen']
    ]
    
    # 删除全空行
    cleaned = [r for r in rows if not all(cell.strip() == '' for cell in r)]
    
    # 缺失值填充
    for r in cleaned:
        for i, cell in enumerate(r):
            if cell.strip() == '':
                r[i] = fillna
    
    return header, cleaned


def normalize_columns(header, data):
    \"\"\"标准化数值列\"\"\"
    num_cols = [i for i, h in enumerate(header) if h.startswith('num_')]
    for idx in num_cols:
        col_vals = [float(r[idx]) for r in data]
        mean = statistics.mean(col_vals)
        stdev = statistics.stdev(col_vals) if len(col_vals) > 1 else 1.0
        for r in data:
            r[idx] = f"{(float(r[idx]) - mean) / stdev:.2f}"
    return data


def print_table(header, data):
    \"\"\"打印表格\"\"\"
    print(' | '.join(header))
    print('-' * 60)
    for row in data:
        print(' | '.join(row))


def giant_cleaner(fillna: str = '0'):
    \"\"\"
    主函数：数据清洗管道
    :param fillna: 缺失值填充值
    :return: list[list[str]] 清洗后的数据
    \"\"\"
    header, cleaned = load_data(fillna)
    cleaned = normalize_columns(header, cleaned)
    print_table(header, cleaned)
    return cleaned


if __name__ == '__main__':
    giant_cleaner()
"""
        split_file.write_text(test_content, encoding='utf-8')
        print(f"✓ 创建测试拆分文件: {split_file}")
    
    # 测试1: 规则评估（不使用LLM）
    print("\n--- 测试1: 规则评估 ---")
    passed, details = validate_split(
        file_orig=str(orig_file),
        file_split=str(split_file),
        function_name="giant_cleaner",
        api_client=None,
        use_llm=False,
        mute=True
    )
    
    print(f"\n结果: {'✓ 通过' if passed else '✗ 失败'}")
    print(f"评分: {details['score']*100:.1f}/100")
    print(f"方法: {details['method']}")
    print(f"原因:\n  {details['reason']}")
    print(f"\n代码结构对比:")
    print(f"  原始: {details['details']['original']['functions']} 个函数, "
          f"{details['details']['original']['code_lines']} 行代码")
    print(f"  拆分: {details['details']['split']['functions']} 个函数, "
          f"{details['details']['split']['code_lines']} 行代码")
    print(f"  相似度: {details['details']['similarity']*100:.1f}%")
    
    # 测试2: LLM评估（如果有API）
    print("\n--- 测试2: LLM评估 ---")
    try:
        client = APIClient()
        passed_llm, details_llm = validate_split(
            file_orig=str(orig_file),
            file_split=str(split_file),
            function_name="giant_cleaner",
            api_client=client,
            use_llm=True,
            mute=True
        )
        
        print(f"\n结果: {'✓ 通过' if passed_llm else '✗ 失败'}")
        print(f"评分: {details_llm['score']*100:.1f}/100")
        print(f"方法: {details_llm['method']}")
        print(f"原因: {details_llm['reason']}")
    except Exception as e:
        print(f"⚠️ LLM评估跳过: {e}")
    
    return passed


def main():
    """主函数"""
    print("\n" + "🧪 验证器功能测试".center(60, "="))
    print()
    
    # 测试sum验证器
    sum_result = test_sum_validator()
    
    # 测试split验证器
    split_result = test_split_validator()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"Sum验证器: {'✓ 通过' if sum_result else '✗ 失败'}")
    print(f"Split验证器: {'✓ 通过' if split_result else '✗ 失败'}")
    
    if sum_result and split_result:
        print("\n✅ 所有验证器测试通过！")
        return 0
    else:
        print("\n⚠️ 部分验证器测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
