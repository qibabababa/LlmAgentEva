#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公共工具函数模块
提供路径处理、文件操作、进程执行等通用功能
"""

import os
import sys
import json
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any


def read_json(path: Union[str, Path]) -> Union[Dict, List]:
    """
    读取JSON文件
    
    Args:
        path: JSON文件路径
        
    Returns:
        解析后的JSON数据
        
    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON格式错误
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(data: Union[Dict, List], path: Union[str, Path], indent: int = 2):
    """
    写入JSON文件
    
    Args:
        data: 要写入的数据
        path: 目标文件路径
        indent: 缩进空格数
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def append_to_json_file(data: Dict, file_path: Union[str, Path]):
    """
    线程安全地追加数据到JSON文件
    
    Args:
        data: 要追加的数据
        file_path: 目标文件路径
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 读取现有数据
    if file_path.exists():
        try:
            existing = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = [existing]
        except json.JSONDecodeError:
            existing = []
    else:
        existing = []
    
    # 追加新数据
    existing.append(data)
    
    # 写回文件
    file_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def safe_path(rel_path: Union[str, Path], base_dir: Union[str, Path]) -> Path:
    """
    安全地将相对路径转换为绝对路径，确保路径在base_dir范围内
    
    Args:
        rel_path: 相对路径
        base_dir: 基础目录
        
    Returns:
        解析后的绝对路径
        
    Raises:
        ValueError: 路径超出base_dir范围
    """
    base_dir = Path(base_dir).resolve()
    rel_path = str(rel_path)
    
    full_path = (base_dir / rel_path).resolve()
    
    # 检查路径是否在base_dir内
    if base_dir not in full_path.parents and full_path != base_dir:
        raise ValueError(f"非法路径: {full_path} 超出工作目录 {base_dir}")
    
    return full_path


def exec_shell(
    cmd: str,
    cwd: Optional[Union[str, Path]] = None,
    extra_env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None
) -> Tuple[int, str, str]:
    """
    执行shell命令
    
    Args:
        cmd: 要执行的命令
        cwd: 工作目录
        extra_env: 额外的环境变量
        timeout: 超时时间（秒）
        
    Returns:
        (返回码, 标准输出, 标准错误)
    """
    args = shlex.split(cmd, posix=(os.name != "nt"))
    
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    return proc.returncode, proc.stdout, proc.stderr


def prepare_venv(venv_dir: Union[str, Path]) -> Path:
    """
    确保虚拟环境存在，并返回bin/Scripts目录路径
    
    Args:
        venv_dir: 虚拟环境目录
        
    Returns:
        bin或Scripts目录的路径
        
    Raises:
        RuntimeError: 虚拟环境结构异常
    """
    venv_dir = Path(venv_dir)
    
    if not venv_dir.exists():
        print(f"[virtualenv] 创建虚拟环境: {venv_dir}")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    
    if not bin_dir.exists():
        raise RuntimeError(f"虚拟环境目录损坏: {bin_dir} 不存在")
    
    return bin_dir.resolve()


def chunk_list(items: List, block: int, size: int = 100) -> Tuple[int, int, List]:
    """
    将列表分块
    
    Args:
        items: 要分块的列表
        block: 当前块编号（从1开始）
        size: 每块大小
        
    Returns:
        (当前块号, 总块数, 当前块的items)
    """
    total_blocks = max(1, (len(items) + size - 1) // size)
    block = max(1, min(block, total_blocks))
    start = (block - 1) * size
    end = start + size
    
    return block, total_blocks, items[start:end]


def dynamic_import(module_path: Union[str, Path], module_name: str = "dynamic_module"):
    """
    动态导入Python模块
    
    Args:
        module_path: 模块文件路径
        module_name: 模块名称
        
    Returns:
        导入的模块对象
        
    Raises:
        FileNotFoundError: 文件不存在
        ImportError: 导入失败
    """
    import importlib.util
    
    module_path = Path(module_path).expanduser().resolve()
    
    if not module_path.exists():
        raise FileNotFoundError(f"找不到文件: {module_path}")
    
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法创建导入规范: {module_path}")
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module


def normalize_output(raw: str) -> str:
    """
    规范化输出字符串，去除无意义的空格差异
    
    Args:
        raw: 原始字符串
        
    Returns:
        规范化后的字符串
    """
    import re
    
    norm_lines = []
    for line in raw.splitlines():
        line = line.strip()
        line = re.sub(r"\[\s+", "[", line)  # "[  " -> "["
        line = re.sub(r"\s+\]", "]", line)  # "  ]" -> "]"
        norm_lines.append(line)
    
    result = "\n".join(norm_lines)
    if raw.endswith("\n"):
        result += "\n"
    
    return result


if __name__ == "__main__":
    # 测试工具函数
    print("测试safe_path:")
    try:
        p = safe_path("test.py", "/tmp")
        print(f"  成功: {p}")
    except ValueError as e:
        print(f"  错误: {e}")
    
    print("\n测试chunk_list:")
    items = list(range(250))
    block, total, chunk = chunk_list(items, 2, 100)
    print(f"  块 {block}/{total}, 包含 {len(chunk)} 个元素")
