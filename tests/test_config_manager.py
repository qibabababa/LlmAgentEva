#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器单元测试
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.config_manager import ConfigManager, get_config


class TestConfigManager:
    """配置管理器测试类"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2, "ConfigManager应该是单例"
    
    def test_load_config(self, tmp_path):
        """测试配置加载"""
        # 创建临时配置文件
        config_content = """
api:
  base_url: "http://test.api.com"
  api_key: "test-key"
  default_model: "test-model"
  temperature: 0.5
  timeout: 300
  max_retries: 2
  stream:
    enabled: true
    fallback_to_non_stream: true

paths:
  project_root: "."
  data_dir: "data"
  tasks_dir: "data/tasks"
  prompts_dir: "data/prompts"
  test_cases_dir: "data/test_cases"
  outputs_dir: "outputs"
  logs_dir: "logs"
  venv_dir: "env"

tasks:
  supported_types:
    - fix_bug
    - convert
  data_dirs:
    fix_bug: "data/tasks/bug_code"
    convert: "data/tasks/code_convert"
  execution:
    max_rounds: 10
    enable_cache: false
    parallel_execution: false
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        
        # 加载配置
        config = ConfigManager()
        config.load_config(str(config_file))
        
        # 验证API配置
        assert config.api.base_url == "http://test.api.com"
        assert config.api.api_key == "test-key"
        assert config.api.default_model == "test-model"
        assert config.api.temperature == 0.5
        assert config.api.timeout == 300
        assert config.api.max_retries == 2
    
    def test_env_override(self, tmp_path, monkeypatch):
        """测试环境变量覆盖"""
        # 创建配置文件
        config_content = """
api:
  base_url: "http://test.api.com"
  api_key: "test-key"
  default_model: "test-model"

paths:
  project_root: "."
  data_dir: "data"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        
        # 设置环境变量
        monkeypatch.setenv("API_KEY", "env-key")
        monkeypatch.setenv("API_BASE_URL", "http://env.api.com")
        
        # 加载配置
        config = ConfigManager()
        config._initialized = False  # 重置初始化状态
        config._config = None
        config.load_config(str(config_file))
        
        # 验证环境变量覆盖
        assert config.api.api_key == "env-key"
        assert config.api.base_url == "http://env.api.com"
    
    def test_get_method(self, tmp_path):
        """测试get方法"""
        config_content = """
api:
  base_url: "http://test.api.com"
  nested:
    value: 123

paths:
  data_dir: "data"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        
        config = ConfigManager()
        config.load_config(str(config_file))
        
        # 测试点号分隔路径
        assert config.get("api.base_url") == "http://test.api.com"
        assert config.get("api.nested.value") == 123
        assert config.get("paths.data_dir") == "data"
        
        # 测试默认值
        assert config.get("nonexistent.key", "default") == "default"
    
    def test_api_config_property(self, tmp_path):
        """测试API配置属性"""
        config_content = """
api:
  base_url: "http://test.api.com"
  api_key: "test-key"
  default_model: "test-model"
  temperature: 0.7
  timeout: 600
  max_retries: 3
  stream:
    enabled: true
    fallback_to_non_stream: true
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)
        
        config = ConfigManager()
        config.load_config(str(config_file))
        
        api_config = config.api
        assert api_config.base_url == "http://test.api.com"
        assert api_config.api_key == "test-key"
        assert api_config.default_model == "test-model"
        assert api_config.temperature == 0.7
        assert api_config.timeout == 600
        assert api_config.max_retries == 3
        assert api_config.stream_enabled is True
        assert api_config.stream_fallback is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
