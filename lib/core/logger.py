"""
统一的日志管理模块

提供全局的日志配置和管理功能，支持：
- 控制台输出
- 文件输出
- 不同日志级别
- 日志轮转
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime


class LoggerManager:
    """日志管理器，提供统一的日志配置"""
    
    _loggers = {}
    _initialized = False
    _log_dir = None
    
    @classmethod
    def initialize(cls, log_dir: Optional[Path] = None, level: int = logging.INFO):
        """
        初始化日志系统
        
        Args:
            log_dir: 日志文件目录，如果为None则只输出到控制台
            level: 日志级别
        """
        if cls._initialized:
            return
        
        cls._log_dir = Path(log_dir) if log_dir else None
        if cls._log_dir:
            cls._log_dir.mkdir(parents=True, exist_ok=True)
        
        cls._initialized = True
    
    @classmethod
    def get_logger(
        cls,
        name: str,
        level: Optional[int] = None,
        log_file: Optional[str] = None
    ) -> logging.Logger:
        """
        获取或创建logger实例
        
        Args:
            name: logger名称，通常使用 __name__
            level: 日志级别，如果为None则使用INFO
            log_file: 日志文件名，如果为None则使用 name.log
        
        Returns:
            配置好的logger实例
        
        Example:
            >>> logger = LoggerManager.get_logger(__name__)
            >>> logger.info("开始执行任务")
        """
        if name in cls._loggers:
            return cls._loggers[name]
        
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(level or logging.INFO)
        logger.propagate = False
        
        # 避免重复添加handler
        if logger.handlers:
            cls._loggers[name] = logger
            return logger
        
        # 创建formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 不再添加控制台handler，所有输出都到文件
        # console_handler = logging.StreamHandler(sys.stdout)
        # console_handler.setLevel(logging.INFO)
        # console_handler.setFormatter(formatter)
        # logger.addHandler(console_handler)
        
        # 添加文件handler（如果配置了log_dir）
        if cls._log_dir:
            if log_file is None:
                log_file = f"{name.replace('.', '_')}.log"
            
            file_path = cls._log_dir / log_file
            
            # 使用RotatingFileHandler实现日志轮转
            # 单个文件最大10MB，保留5个备份
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def get_evaluation_logger(cls) -> logging.Logger:
        """获取评测专用logger"""
        return cls.get_logger('evaluation', log_file='evaluation.log')
    
    @classmethod
    def get_api_logger(cls) -> logging.Logger:
        """获取API调用专用logger"""
        return cls.get_logger('api', log_file='api.log')
    
    @classmethod
    def get_tool_logger(cls) -> logging.Logger:
        """获取工具执行专用logger"""
        return cls.get_logger('tool_execution', log_file='tool_execution.log')
    
    @classmethod
    def shutdown(cls):
        """关闭所有logger，刷新缓冲区"""
        for logger in cls._loggers.values():
            for handler in logger.handlers:
                handler.close()
        cls._loggers.clear()
        cls._initialized = False


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    便捷函数：获取logger实例
    
    Args:
        name: logger名称
        level: 日志级别
    
    Returns:
        配置好的logger实例
    
    Example:
        >>> from lib.core.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("任务开始")
    """
    return LoggerManager.get_logger(name, level)


# 用于记录API调用详情的特殊格式化器
class APICallFormatter(logging.Formatter):
    """API调用专用的格式化器，输出更详细的信息"""
    
    def format(self, record):
        # 基础格式
        result = super().format(record)
        
        # 如果有额外的API信息，添加到日志中
        if hasattr(record, 'api_info'):
            api_info = record.api_info
            result += f"\n  模型: {api_info.get('model', 'N/A')}"
            result += f"\n  延迟: {api_info.get('latency', 'N/A')}秒"
            result += f"\n  Tokens: {api_info.get('tokens', 'N/A')}"
            if 'error' in api_info:
                result += f"\n  错误: {api_info['error']}"
        
        return result


def log_api_call(logger: logging.Logger, level: int, message: str, **api_info):
    """
    记录API调用，附带详细信息
    
    Args:
        logger: logger实例
        level: 日志级别
        message: 日志消息
        **api_info: API调用的详细信息（model, latency, tokens等）
    
    Example:
        >>> logger = get_logger(__name__)
        >>> log_api_call(
        ...     logger, logging.INFO, "API调用成功",
        ...     model="qwen3-235b", latency=2.5, tokens=150
        ... )
    """
    extra = {'api_info': api_info}
    logger.log(level, message, extra=extra)


if __name__ == '__main__':
    # 测试代码
    from pathlib import Path
    
    # 初始化日志系统
    test_log_dir = Path('/tmp/test_logs')
    LoggerManager.initialize(test_log_dir, logging.DEBUG)
    
    # 测试基本日志
    logger = get_logger('test_module')
    logger.debug("这是debug消息")
    logger.info("这是info消息")
    logger.warning("这是warning消息")
    logger.error("这是error消息")
    
    # 测试API日志
    api_logger = LoggerManager.get_api_logger()
    log_api_call(
        api_logger, logging.INFO, "API调用成功",
        model="qwen3-235b",
        latency=2.5,
        tokens=150
    )
    
    # 测试评测日志
    eval_logger = LoggerManager.get_evaluation_logger()
    eval_logger.info("评测任务开始")
    eval_logger.info("评测任务完成")
    
    print(f"\n日志文件已创建在: {test_log_dir}")
    print(f"文件列表: {list(test_log_dir.glob('*.log'))}")
    
    LoggerManager.shutdown()
