#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
输出控制模块

控制是否显示详细信息，避免终端刷屏
"""

class OutputControl:
    """
    全局输出控制器
    
    控制是否显示详细信息（模型输出、代码内容等）
    """
    
    _show_details: bool = False  # 默认不显示详细信息
    
    @classmethod
    def set_show_details(cls, show: bool):
        """设置是否显示详细信息"""
        cls._show_details = show
    
    @classmethod
    def should_show_details(cls) -> bool:
        """是否应该显示详细信息"""
        return cls._show_details
    
    @classmethod
    def print_detail(cls, *args, **kwargs):
        """打印详细信息（仅在启用时）"""
        if cls._show_details:
            print(*args, **kwargs)


# 便捷函数
def set_show_details(show: bool):
    """设置是否显示详细信息"""
    OutputControl.set_show_details(show)


def should_show_details() -> bool:
    """是否应该显示详细信息"""
    return OutputControl.should_show_details()


def print_detail(*args, **kwargs):
    """打印详细信息（仅在启用时）"""
    OutputControl.print_detail(*args, **kwargs)
