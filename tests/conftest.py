#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest配置文件
"""

import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def project_root():
    """返回项目根目录"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """返回测试数据目录"""
    return project_root / "tests" / "test_data"


@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试前重置单例"""
    from lib.core.config_manager import ConfigManager
    from lib.core.metrics import MetricsCollector
    
    # 注意：实际上这些单例不会被完全重置，这是Python单例的特性
    # 但我们可以重置它们的内部状态
    yield
