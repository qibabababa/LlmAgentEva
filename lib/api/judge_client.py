#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Judge API客户端
用于评估sum和split任务结果的专用LLM客户端
与被测试模型分离，避免自己评估自己
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.api.client import APIClient
from lib.core.config_manager import get_config
from lib.core.logger import get_logger

logger = get_logger(__name__)


class JudgeClient:
    """
    Judge API客户端
    
    用于评估任务结果的专用LLM，配置独立于被测试模型
    """
    
    def __init__(self):
        """初始化Judge客户端"""
        self.config = get_config()
        self.judge_config_dict = self.config.get('evaluation', {}).get('judge_model', {})
        
        # 检查是否启用LLM评估
        if not self.judge_config_dict.get('enabled', False):
            logger.info("Judge模型未启用，将使用规则评估")
            self._api_client = None
            return
        
        # 获取Judge模型配置
        api_key = self.judge_config_dict.get('api_key') or self.config.get('api', {}).get('api_key')
        base_url = self.judge_config_dict.get('base_url') or self.config.get('api', {}).get('base_url')
        model = self.judge_config_dict.get('model', 'gpt-4')
        
        # 检查配置完整性
        if not api_key or api_key == "your-judge-api-key-here":
            logger.warning("Judge API Key未配置，将使用规则评估")
            self._api_client = None
            return
        
        # 创建API客户端
        try:
            self._api_client = APIClient(
                api_url=base_url,  # 注意：APIClient参数名是api_url不是base_url
                api_key=api_key,
                model=model,
                timeout=self.judge_config_dict.get('timeout', 30)
            )
            
            # 手动设置max_retries（APIClient初始化时会读取配置，这里覆盖）
            self._api_client.max_retries = self.judge_config_dict.get('max_retries', 2)
            
            logger.info(
                f"Judge客户端已初始化: "
                f"model={model}, "
                f"timeout={self.judge_config_dict.get('timeout', 30)}s"
            )
        except Exception as e:
            logger.error(f"Judge客户端初始化失败: {e}")
            self._api_client = None
    
    @property
    def available(self) -> bool:
        """判断Judge客户端是否可用"""
        return self._api_client is not None
    
    @property
    def fallback_to_rules(self) -> bool:
        """判断失败时是否回退到规则评估"""
        return self.judge_config_dict.get('fallback_to_rules', True)
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用Judge模型进行评估
        
        Args:
            messages: 消息列表
            temperature: 温度（默认使用配置值）
            max_tokens: 最大token数（默认使用配置值）
            **kwargs: 其他参数
        
        Returns:
            API响应
        
        Raises:
            RuntimeError: Judge客户端不可用
            APIError: API调用失败
        """
        if not self.available:
            raise RuntimeError("Judge客户端不可用")
        
        # 使用Judge配置的默认参数
        if temperature is None:
            temperature = self.judge_config_dict.get('temperature', 0.1)
        if max_tokens is None:
            max_tokens = self.judge_config_dict.get('max_tokens', 200)
        
        logger.debug(f"调用Judge模型: temperature={temperature}, max_tokens={max_tokens}")
        
        # 调用API
        response = self._api_client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,  # Judge评估不使用流式
            **kwargs
        )
        
        return response
    
    def evaluate_with_fallback(
        self,
        messages: List[Dict[str, str]],
        fallback_func: callable,
        **kwargs
    ) -> tuple:
        """
        尝试LLM评估，失败时可选择回退到规则评估
        
        Args:
            messages: 评估消息
            fallback_func: 回退函数（规则评估）
            **kwargs: 传递给回退函数的参数
        
        Returns:
            (是否通过, 评分, 原因, 使用的方法)
        """
        # 如果Judge不可用
        if not self.available:
            logger.info("Judge不可用，使用规则评估")
            passed, score, reason = fallback_func(**kwargs)
            return passed, score, reason, 'rules'
        
        # 尝试LLM评估
        try:
            response = self.chat_completion(messages)
            
            # 解析响应
            message = response['choices'][0]['message']
            content = message.get('content') or message.get('reasoning_content', '')
            
            # 这里需要解析JSON等，由调用方处理
            # 返回原始响应给调用方解析
            return response, None, None, 'llm'
            
        except Exception as e:
            logger.warning(f"Judge评估失败: {e}")
            
            # 根据配置决定是否回退
            if self.fallback_to_rules:
                logger.info("回退到规则评估")
                passed, score, reason = fallback_func(**kwargs)
                return passed, score, reason, 'rules'
            else:
                # 不回退，直接返回失败
                return False, 0.0, f"Judge评估失败: {e}", 'failed'


def get_judge_client() -> JudgeClient:
    """
    获取Judge客户端单例
    
    Returns:
        JudgeClient实例
    """
    if not hasattr(get_judge_client, '_instance'):
        get_judge_client._instance = JudgeClient()
    return get_judge_client._instance


# 便捷函数
def is_judge_available() -> bool:
    """判断Judge客户端是否可用"""
    return get_judge_client().available


if __name__ == "__main__":
    # 测试Judge客户端
    print("测试Judge客户端...")
    
    judge = get_judge_client()
    
    print(f"Judge可用: {judge.available}")
    print(f"失败时回退到规则: {judge.fallback_to_rules}")
    
    if judge.available:
        try:
            response = judge.chat_completion([
                {"role": "user", "content": "Say hello"}
            ])
            print(f"✓ Judge API调用成功")
            print(f"  Model: {response.get('model')}")
        except Exception as e:
            print(f"✗ Judge API调用失败: {e}")
    else:
        print("Judge客户端不可用，将使用规则评估")
