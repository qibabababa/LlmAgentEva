#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证器模块
提供各种任务类型的验证器
"""

from pathlib import Path
from typing import Dict, Type, Optional


class BaseValidator:
    """基础验证器类"""
    
    def validate(self, **kwargs) -> bool:
        """
        验证结果
        
        Returns:
            是否通过验证
        """
        raise NotImplementedError


# 验证器注册表
_VALIDATORS: Dict[str, Type[BaseValidator]] = {}


def register_validator(task_type: str):
    """
    验证器注册装饰器
    
    使用方式:
        @register_validator("fix_bug")
        class BugCodeValidator(BaseValidator):
            pass
    """
    def decorator(cls):
        _VALIDATORS[task_type] = cls
        return cls
    return decorator


def get_validator(task_type: str) -> Optional[BaseValidator]:
    """
    获取指定任务类型的验证器
    
    Args:
        task_type: 任务类型
        
    Returns:
        验证器实例，如果不存在返回None
    """
    validator_class = _VALIDATORS.get(task_type)
    if validator_class:
        return validator_class()
    return None


def list_validators() -> list:
    """列出所有已注册的验证器"""
    return list(_VALIDATORS.keys())


# 导入所有验证器以触发注册
# 注意: 这些模块需要使用 @register_validator 装饰器

try:
    from . import bugcode
    from . import convert
    from . import refactor
    from . import env
    from . import summary
    from . import split
except ImportError as e:
    print(f"警告: 部分验证器导入失败: {e}")


__all__ = [
    'BaseValidator',
    'register_validator',
    'get_validator',
    'list_validators',
]
