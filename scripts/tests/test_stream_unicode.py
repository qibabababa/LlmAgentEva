#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试流式API的UTF-8解码
验证修复是否有效
"""

import sys
import io
from unittest.mock import Mock, patch


def simulate_chunked_utf8():
    """
    模拟UTF-8字符被截断的场景
    """
    # 测试字符串（包含中文、emoji）
    test_text = "Hello 你好 世界 🌍 测试 UTF-8 编码"
    
    # 将字符串编码为UTF-8字节
    utf8_bytes = test_text.encode('utf-8')
    
    print(f"原始文本: {test_text}")
    print(f"UTF-8字节数: {len(utf8_bytes)}")
    print(f"UTF-8 (hex): {utf8_bytes.hex()}")
    print()
    
    # 模拟不同的chunk分割方式
    test_cases = [
        {
            "name": "正常分割（不截断字符）",
            "chunks": [utf8_bytes[:10], utf8_bytes[10:20], utf8_bytes[20:]]
        },
        {
            "name": "截断中文字符（3字节）",
            "chunks": [utf8_bytes[:8], utf8_bytes[8:15], utf8_bytes[15:]]  # 可能截断"你"
        },
        {
            "name": "截断emoji（4字节）",
            "chunks": [utf8_bytes[:19], utf8_bytes[19:25], utf8_bytes[25:]]  # 可能截断🌍
        },
        {
            "name": "极小chunk（模拟网络抖动）",
            "chunks": [utf8_bytes[i:i+1] for i in range(len(utf8_bytes))]  # 每次1字节
        }
    ]
    
    for case in test_cases:
        print(f"测试用例: {case['name']}")
        print("-" * 60)
        
        # 测试旧方法（直接解码）
        print("【旧方法 - 直接解码】")
        try:
            result_old = ""
            for i, chunk in enumerate(case['chunks']):
                chunk_text = chunk.decode('utf-8')  # 可能失败
                result_old += chunk_text
                print(f"  Chunk {i+1}: 解码成功 ({len(chunk)} bytes)")
            
            if result_old == test_text:
                print("  ✅ 结果正确")
            else:
                print(f"  ❌ 结果错误: {result_old}")
        except UnicodeDecodeError as e:
            print(f"  ❌ 解码失败: {e}")
        
        print()
        
        # 测试新方法（字节缓冲区）
        print("【新方法 - 字节缓冲区】")
        try:
            result_new = ""
            byte_buffer = b""
            
            for i, chunk in enumerate(case['chunks']):
                byte_buffer += chunk
                
                try:
                    chunk_text = byte_buffer.decode('utf-8')
                    byte_buffer = b""
                    result_new += chunk_text
                    print(f"  Chunk {i+1}: 解码成功 ({len(chunk)} bytes)")
                except UnicodeDecodeError as e:
                    print(f"  Chunk {i+1}: 字符被截断，等待下一个chunk ({len(chunk)} bytes)")
                    continue
            
            # 处理残留字节
            if byte_buffer:
                print(f"  警告: 有残留字节 ({len(byte_buffer)} bytes)")
                chunk_text = byte_buffer.decode('utf-8', errors='ignore')
                result_new += chunk_text
            
            if result_new == test_text:
                print("  ✅ 结果正确")
            else:
                print(f"  ❌ 结果错误: {result_new}")
        except Exception as e:
            print(f"  ❌ 意外错误: {e}")
        
        print()
        print("=" * 60)
        print()


def test_real_api():
    """
    测试真实API（如果配置了）
    """
    print("【测试真实API】")
    print("-" * 60)
    
    try:
        from lib.api.client import APIClient
        from lib.core.config_manager import get_config
        
        config = get_config()
        
        if not config.api.api_key or config.api.api_key == "your-api-key-here":
            print("⚠️  未配置API密钥，跳过真实API测试")
            return
        
        client = APIClient()
        
        # 测试消息（包含中文）
        messages = [
            {"role": "user", "content": "请用中文回答：你好，介绍一下你自己。包含一些emoji表情。"}
        ]
        
        print("发起流式API请求...")
        try:
            stream = client.chat_completion_stream(messages)
            result = client.reconstruct_from_stream(stream)
            
            content = result['choices'][0]['message']['content']
            print(f"✅ 流式API成功")
            print(f"响应内容: {content[:100]}...")
            
        except Exception as e:
            print(f"❌ 流式API失败: {e}")
    
    except ImportError as e:
        print(f"⚠️  无法导入API客户端: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("流式API UTF-8解码测试")
    print("=" * 60)
    print()
    
    # 1. 模拟测试
    simulate_chunked_utf8()
    
    # 2. 真实API测试（可选）
    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        test_real_api()
    else:
        print("提示: 使用 --real 参数可以测试真实API")
        print("例如: python scripts/test_stream_unicode.py --real")
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
