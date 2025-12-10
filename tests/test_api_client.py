#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API客户端单元测试
"""

import sys
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.api.client import APIClient, APIError


class TestAPIClient:
    """API客户端测试类"""
    
    @patch('lib.api.client.get_config')
    def test_client_initialization(self, mock_config):
        """测试客户端初始化"""
        # Mock配置
        mock_api_config = Mock()
        mock_api_config.base_url = "http://test.api.com"
        mock_api_config.api_key = "test-key"
        mock_api_config.default_model = "test-model"
        mock_api_config.timeout = 600
        mock_api_config.temperature = 0.7
        mock_api_config.max_retries = 3
        
        mock_config.return_value.api = mock_api_config
        
        # 创建客户端
        client = APIClient()
        
        assert client.api_url == "http://test.api.com"
        assert client.api_key == "test-key"
        assert client.model == "test-model"
        assert client.timeout == 600
        assert client.temperature == 0.7
        assert client.max_retries == 3
    
    @patch('lib.api.client.get_config')
    @patch('lib.api.client.requests.post')
    def test_chat_completion_success(self, mock_post, mock_config):
        """测试聊天补全成功"""
        # Mock配置
        mock_api_config = Mock()
        mock_api_config.base_url = "http://test.api.com"
        mock_api_config.api_key = "test-key"
        mock_api_config.default_model = "test-model"
        mock_api_config.timeout = 600
        mock_api_config.temperature = 0.7
        mock_api_config.max_retries = 3
        
        mock_config.return_value.api = mock_api_config
        
        # Mock响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test-id",
            "model": "test-model",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Test response"
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        mock_post.return_value = mock_response
        
        # 调用API
        client = APIClient()
        messages = [{"role": "user", "content": "Test"}]
        response = client.chat_completion(messages)
        
        # 验证
        assert response["id"] == "test-id"
        assert response["choices"][0]["message"]["content"] == "Test response"
        assert response["usage"]["total_tokens"] == 15
        
        # 验证调用参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://test.api.com"
        assert call_args[1]["json"]["messages"] == messages
    
    @patch('lib.api.client.get_config')
    @patch('lib.api.client.requests.post')
    def test_chat_completion_api_error(self, mock_post, mock_config):
        """测试API错误"""
        # Mock配置
        mock_api_config = Mock()
        mock_api_config.base_url = "http://test.api.com"
        mock_api_config.api_key = "test-key"
        mock_api_config.default_model = "test-model"
        mock_api_config.timeout = 600
        mock_api_config.temperature = 0.7
        mock_api_config.max_retries = 3
        
        mock_config.return_value.api = mock_api_config
        
        # Mock错误响应
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        mock_post.return_value = mock_response
        
        # 调用API应该抛出异常
        client = APIClient()
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(APIError) as exc_info:
            client.chat_completion(messages)
        
        assert exc_info.value.status_code == 429
    
    @patch('lib.api.client.get_config')
    def test_reconstruct_from_stream(self, mock_config):
        """测试从流重构响应"""
        # Mock配置
        mock_api_config = Mock()
        mock_api_config.base_url = "http://test.api.com"
        mock_api_config.api_key = "test-key"
        mock_api_config.default_model = "test-model"
        mock_api_config.timeout = 600
        mock_api_config.temperature = 0.7
        mock_api_config.max_retries = 3
        
        mock_config.return_value.api = mock_api_config
        
        # 模拟流式响应
        stream = [
            {
                "id": "test-id",
                "model": "test-model",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": "Hello"},
                    "finish_reason": None
                }]
            },
            {
                "id": "test-id",
                "choices": [{
                    "index": 0,
                    "delta": {"content": " World"},
                    "finish_reason": None
                }]
            },
            {
                "id": "test-id",
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
        ]
        
        # 重构响应
        client = APIClient()
        response = client.reconstruct_from_stream(iter(stream))
        
        # 验证
        assert response["id"] == "test-id"
        assert response["model"] == "test-model"
        assert response["choices"][0]["message"]["content"] == "Hello World"
        assert response["choices"][0]["finish_reason"] == "stop"
    
    @patch('lib.api.client.get_config')
    def test_custom_parameters(self, mock_config):
        """测试自定义参数"""
        # Mock配置
        mock_api_config = Mock()
        mock_api_config.base_url = "http://test.api.com"
        mock_api_config.api_key = "test-key"
        mock_api_config.default_model = "test-model"
        mock_api_config.timeout = 600
        mock_api_config.temperature = 0.7
        mock_api_config.max_retries = 3
        
        mock_config.return_value.api = mock_api_config
        
        # 使用自定义参数创建客户端
        custom_client = APIClient(
            api_url="http://custom.api.com",
            api_key="custom-key",
            model="custom-model",
            timeout=300
        )
        
        assert custom_client.api_url == "http://custom.api.com"
        assert custom_client.api_key == "custom-key"
        assert custom_client.model == "custom-model"
        assert custom_client.timeout == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
