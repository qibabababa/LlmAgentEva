#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Judge模型配置
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.api.judge_client import get_judge_client
from lib.core.config_manager import get_config


def test_judge_config():
    """测试Judge配置"""
    print("=" * 60)
    print("Judge模型配置测试")
    print("=" * 60)
    print()
    
    # 加载配置
    config = get_config()
    judge_config = config.get('evaluation', {}).get('judge_model', {})
    
    print("📋 配置信息:")
    print(f"  启用: {judge_config.get('enabled', False)}")
    print(f"  模型: {judge_config.get('model', 'N/A')}")
    api_key = judge_config.get('api_key', '')
    print(f"  API Key: {'已配置' if api_key and api_key != 'your-judge-api-key-here' else '未配置'}")
    print(f"  Base URL: {judge_config.get('base_url') or '使用主API配置'}")
    print(f"  温度: {judge_config.get('temperature', 0.1)}")
    print(f"  超时: {judge_config.get('timeout', 30)}秒")
    print(f"  最大Token: {judge_config.get('max_tokens', 200)}")
    print(f"  重试次数: {judge_config.get('max_retries', 2)}")
    print(f"  失败回退: {judge_config.get('fallback_to_rules', True)}")
    print()
    
    # 获取Judge客户端
    judge = get_judge_client()
    
    print("🔍 Judge客户端状态:")
    print(f"  可用: {judge.available}")
    
    if not judge.available:
        print("  ⚠️ Judge客户端不可用")
        print("  原因可能是:")
        print("    1. JUDGE_ENABLED=false")
        print("    2. Judge API Key未配置")
        print("    3. API Key是模板值")
        print()
        print("  将自动回退到规则评估")
        return False
    
    print(f"  ✓ Judge客户端已初始化")
    print()
    
    # 测试API调用
    print("🧪 测试Judge API调用:")
    try:
        response = judge.chat_completion([
            {"role": "user", "content": "Say hello in one word"}
        ], max_tokens=10)
        
        print("  ✓ API调用成功")
        print(f"  模型: {response.get('model', 'Unknown')}")
        
        # 提取响应内容
        message = response['choices'][0]['message']
        content = message.get('content') or message.get('reasoning_content', '')
        print(f"  响应: {content[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"  ✗ API调用失败: {e}")
        print()
        
        if judge.fallback_to_rules:
            print("  ✓ 已配置回退到规则评估")
        else:
            print("  ⚠️ 未配置回退，任务可能失败")
        
        return False


def show_recommendations():
    """显示配置建议"""
    print()
    print("=" * 60)
    print("💡 配置建议")
    print("=" * 60)
    print()
    
    judge = get_judge_client()
    config = get_config()
    
    if not judge.available:
        print("当前Judge不可用，建议配置：")
        print()
        print("方式1: 编辑 .env 文件，添加:")
        print("  JUDGE_ENABLED=true")
        print("  JUDGE_API_KEY=your-actual-api-key")
        print("  JUDGE_API_BASE_URL=https://api.openai.com/v1/chat/completions")
        print("  JUDGE_MODEL=gpt-4")
        print()
        print("方式2: 使用规则评估（免费）:")
        print("  JUDGE_ENABLED=false")
        print()
    else:
        print("✓ Judge配置正常！")
        print()
        print("当前配置:")
        test_model = config.get('api', {}).get('default_model', 'N/A')
        judge_model = config.get('evaluation', {}).get('judge_model', {}).get('model', 'N/A')
        print(f"  被测试模型: {test_model}")
        print(f"  Judge模型: {judge_model}")
        print()
        
        if test_model == judge_model:
            print("⚠️ 注意: 被测试模型和Judge模型相同")
            print("  建议使用不同的模型避免自我评估偏见")
        else:
            print("✓ 被测试模型和Judge模型已分离")
        print()
    
    print("详细配置文档: docs/JUDGE_MODEL_CONFIG.md")


def main():
    """主函数"""
    success = test_judge_config()
    show_recommendations()
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    
    if success:
        print("✅ Judge配置正常，可以开始评测")
        return 0
    else:
        print("⚠️ Judge不可用，将使用规则评估")
        return 1


if __name__ == "__main__":
    sys.exit(main())
