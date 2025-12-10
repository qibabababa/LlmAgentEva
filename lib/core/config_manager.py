#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理所有配置项
支持从环境变量和.env文件加载敏感信息
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass

# 尝试导入 python-dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


@dataclass
class APIConfig:
    """API配置"""
    base_url: str
    api_key: str
    default_model: str
    temperature: float = 0.7
    timeout: int = 600
    max_retries: int = 3
    stream_enabled: bool = True
    stream_fallback: bool = True


@dataclass
class PathsConfig:
    """路径配置"""
    project_root: Path
    data_dir: Path
    tasks_dir: Path
    prompts_dir: Path
    test_cases_dir: Path
    outputs_dir: Path
    logs_dir: Path
    venv_dir: Path


@dataclass
class TasksConfig:
    """任务配置"""
    supported_types: list
    data_dirs: Dict[str, Path]
    max_rounds: int = 15
    enable_cache: bool = False
    parallel_execution: bool = False


class ConfigManager:
    """
    配置管理器
    单例模式，全局唯一实例
    """
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            # 加载.env文件（如果存在）
            self._load_dotenv()
            # 加载配置
            self.load_config()
    
    def _load_dotenv(self):
        """加载.env文件"""
        if not DOTENV_AVAILABLE:
            return
        
        # 查找.env文件
        env_paths = [
            Path.cwd() / ".env",
            Path(__file__).parent.parent.parent / ".env",
        ]
        
        # 同时支持环境特定的.env文件
        env_name = os.getenv('EVAL_ENV', 'dev')
        env_specific_paths = [
            Path.cwd() / f".env.{env_name}",
            Path(__file__).parent.parent.parent / f".env.{env_name}",
        ]
        
        # 先加载通用.env，再加载环境特定.env（后者会覆盖前者）
        for path in env_paths + env_specific_paths:
            if path.exists():
                load_dotenv(path, override=True)
                print(f"✓ 已加载环境变量文件: {path}")
    
    def load_config(self, config_file: Optional[str] = None):
        """
        加载配置文件
        
        Args:
            config_file: 配置文件路径，默认为 config/config.yaml
        """
        if config_file is None:
            # 查找配置文件
            config_file = self._find_config_file()
        
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        # 加载YAML配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # 解析项目根目录
        if config_path.parent.name == 'config':
            self._project_root = config_path.parent.parent
        else:
            self._project_root = config_path.parent
        
        # 处理环境变量覆盖
        self._apply_env_overrides()
        
        # 加载环境特定配置
        self._load_environment_config()
        
        print(f"✓ 配置已加载: {config_path}")
    
    def _find_config_file(self) -> Path:
        """查找配置文件"""
        # 按优先级查找配置文件
        search_paths = [
            Path.cwd() / "config" / "config.yaml",
            Path.cwd() / "config.yaml",
            Path(__file__).parent.parent.parent / "config" / "config.yaml",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        raise FileNotFoundError("找不到配置文件 config.yaml")
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        # API配置环境变量映射
        env_mappings = {
            # 主API配置
            'API_KEY': ('api', 'api_key'),
            'API_BASE_URL': ('api', 'base_url'),
            'API_MODEL': ('api', 'default_model'),
            'API_TEMPERATURE': ('api', 'temperature', float),
            'API_TIMEOUT': ('api', 'timeout', int),
            'API_MAX_RETRIES': ('api', 'max_retries', int),
            'STREAM_ENABLED': ('api', 'stream', 'enabled', lambda x: x.lower() in ('true', '1', 'yes')),
            'STREAM_FALLBACK': ('api', 'stream', 'fallback_to_non_stream', lambda x: x.lower() in ('true', '1', 'yes')),
            
            # 评估模型配置（Judge Model）
            'JUDGE_ENABLED': ('evaluation', 'judge_model', 'enabled', lambda x: x.lower() in ('true', '1', 'yes')),
            'JUDGE_API_KEY': ('evaluation', 'judge_model', 'api_key'),
            'JUDGE_API_BASE_URL': ('evaluation', 'judge_model', 'base_url'),
            'JUDGE_MODEL': ('evaluation', 'judge_model', 'model'),
            'JUDGE_TEMPERATURE': ('evaluation', 'judge_model', 'temperature', float),
            'JUDGE_TIMEOUT': ('evaluation', 'judge_model', 'timeout', int),
            'JUDGE_MAX_TOKENS': ('evaluation', 'judge_model', 'max_tokens', int),
            'JUDGE_MAX_RETRIES': ('evaluation', 'judge_model', 'max_retries', int),
            'JUDGE_FALLBACK_TO_RULES': ('evaluation', 'judge_model', 'fallback_to_rules', lambda x: x.lower() in ('true', '1', 'yes')),
            
            # 兼容旧的环境变量名
            'OPENAI_API_URL': ('api', 'base_url'),
            'OPENAI_API_KEY': ('api', 'api_key'),
            'DEFAULT_MODEL': ('api', 'default_model'),
        }
        
        for env_var, config_path in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                
                # 如果有类型转换函数
                if len(config_path) > 2 and callable(config_path[-1]):
                    converter = config_path[-1]
                    config_path = config_path[:-1]
                    try:
                        value = converter(value)
                    except (ValueError, TypeError) as e:
                        print(f"⚠️  环境变量 {env_var} 转换失败: {e}")
                        continue
                elif len(config_path) > 2 and isinstance(config_path[-1], type):
                    converter = config_path[-1]
                    config_path = config_path[:-1]
                    try:
                        value = converter(value)
                    except (ValueError, TypeError) as e:
                        print(f"⚠️  环境变量 {env_var} 转换失败: {e}")
                        continue
                
                # 设置配置值
                config_dict = self._config
                for key in config_path[:-1]:
                    if key not in config_dict:
                        config_dict[key] = {}
                    config_dict = config_dict[key]
                config_dict[config_path[-1]] = value
                
                # 只显示部分敏感信息
                if 'key' in env_var.lower() and len(str(value)) > 10:
                    display_value = f"{str(value)[:6]}...{str(value)[-4:]}"
                else:
                    display_value = value
                print(f"✓ 环境变量覆盖: {'.'.join(config_path)} = {display_value}")
    
    def _load_environment_config(self):
        """加载环境特定配置（dev/test/prod）"""
        env_name = self._config.get('environments', {}).get('current', 'default')
        if env_name == 'default':
            return
        
        env_config_file = self._project_root / "config" / "environments" / f"{env_name}.yaml"
        if env_config_file.exists():
            with open(env_config_file, 'r', encoding='utf-8') as f:
                env_config = yaml.safe_load(f)
            
            # 深度合并配置
            self._deep_merge(self._config, env_config)
            print(f"✓ 环境配置已加载: {env_name}")
    
    def _deep_merge(self, base: dict, override: dict):
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项（支持点号分隔的路径）
        
        Args:
            key: 配置键，如 "api.base_url"
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def _resolve_path(self, path: str) -> Path:
        """解析相对路径为绝对路径"""
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return (self._project_root / path).resolve()
    
    @property
    def api(self) -> APIConfig:
        """获取API配置"""
        api_cfg = self._config['api']
        return APIConfig(
            base_url=api_cfg['base_url'],
            api_key=api_cfg['api_key'],
            default_model=api_cfg['default_model'],
            temperature=api_cfg.get('temperature', 0.7),
            timeout=api_cfg.get('timeout', 600),
            max_retries=api_cfg.get('max_retries', 3),
            stream_enabled=api_cfg.get('stream', {}).get('enabled', True),
            stream_fallback=api_cfg.get('stream', {}).get('fallback_to_non_stream', True)
        )
    
    @property
    def paths(self) -> PathsConfig:
        """获取路径配置"""
        paths_cfg = self._config['paths']
        return PathsConfig(
            project_root=self._project_root,
            data_dir=self._resolve_path(paths_cfg['data_dir']),
            tasks_dir=self._resolve_path(paths_cfg['tasks_dir']),
            prompts_dir=self._resolve_path(paths_cfg['prompts_dir']),
            test_cases_dir=self._resolve_path(paths_cfg['test_cases_dir']),
            outputs_dir=self._resolve_path(paths_cfg['outputs_dir']),
            logs_dir=self._resolve_path(paths_cfg['logs_dir']),
            venv_dir=self._resolve_path(paths_cfg['venv_dir'])
        )
    
    @property
    def tasks(self) -> TasksConfig:
        """获取任务配置"""
        tasks_cfg = self._config['tasks']
        
        # 解析数据目录路径
        data_dirs = {}
        for key, path in tasks_cfg['data_dirs'].items():
            data_dirs[key] = self._resolve_path(path)
        
        return TasksConfig(
            supported_types=tasks_cfg['supported_types'],
            data_dirs=data_dirs,
            max_rounds=tasks_cfg['execution'].get('max_rounds', 15),
            enable_cache=tasks_cfg['execution'].get('enable_cache', False),
            parallel_execution=tasks_cfg['execution'].get('parallel_execution', False)
        )
    
    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return self._project_root
    
    def ensure_directories(self):
        """确保所有必要的目录存在"""
        paths = self.paths
        directories = [
            paths.data_dir,
            paths.tasks_dir,
            paths.prompts_dir,
            paths.test_cases_dir,
            paths.outputs_dir,
            paths.logs_dir,
        ]
        
        for task_dir in self.tasks.data_dirs.values():
            directories.append(task_dir)
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        print(f"✓ 所有目录已创建")
    
    def print_config(self):
        """打印当前配置（隐藏敏感信息）"""
        print("\n" + "=" * 60)
        print("当前配置")
        print("=" * 60)
        
        # API配置
        api = self.api
        print(f"\nAPI配置:")
        print(f"  URL: {api.base_url}")
        print(f"  API Key: {api.api_key[:10]}...{api.api_key[-4:]}")
        print(f"  默认模型: {api.default_model}")
        print(f"  温度: {api.temperature}")
        print(f"  超时: {api.timeout}秒")
        print(f"  流式: {'启用' if api.stream_enabled else '禁用'}")
        
        # 路径配置
        paths = self.paths
        print(f"\n路径配置:")
        print(f"  项目根目录: {paths.project_root}")
        print(f"  数据目录: {paths.data_dir}")
        print(f"  输出目录: {paths.outputs_dir}")
        print(f"  日志目录: {paths.logs_dir}")
        
        # 任务配置
        tasks = self.tasks
        print(f"\n任务配置:")
        print(f"  支持的任务类型: {', '.join(tasks.supported_types)}")
        print(f"  最大轮数: {tasks.max_rounds}")
        
        print("\n" + "=" * 60)


# 全局配置实例
_config_manager = None


def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config(config_file: Optional[str] = None):
    """重新加载配置"""
    global _config_manager
    _config_manager = ConfigManager()
    _config_manager.load_config(config_file)
    return _config_manager


if __name__ == "__main__":
    # 测试配置加载
    config = get_config()
    config.print_config()
    config.ensure_directories()
