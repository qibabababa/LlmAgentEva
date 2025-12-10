#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tool_call_runner.py
解析并执行工具调用结果：
  execute_command / read_file / list_files / replace_in_file
  write_to_file / ask_followup_question / search_files
  return_content
运行方式：
  python tool_call_runner.py [--base-dir /path/to/dir] < tool_calls.json
  或
  python tool_call_runner.py [--base-dir /path/to/dir] tool_calls.json
"""

import os
import re
import sys
import ast
import glob
import json
import shlex
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple , Optional

import subprocess

# 导入公共模块
from lib.core.utils import safe_path, exec_shell, prepare_venv, chunk_list
from lib.core.diff_utils import apply_diff, DiffApplyError

# 默认基础目录（独立运行时使用）
DEFAULT_BASE_DIR = Path.cwd()

def _abs_path(rel_path: str, base_dir) -> Path:
    """把相对路径转换为绝对路径（限制在 base_dir 内）"""
    return safe_path(rel_path, base_dir)
def _prepare_venv(venv_dir: Path) -> Path:
    """确保 venv_dir/.venv 存在并返回其 bin|Scripts 路径"""
    return prepare_venv(venv_dir)


# exec_shell已移至utils.py

# -----------------------------------------------------------------------------


def handle_execute(tool_call: Dict, base_dir: Path, *, env: bool = False, venv_path: Optional[Path] = None) -> Dict:
    args = json.loads(tool_call["function"]["arguments"])
    cmd = args.get("command", "").strip()
    need_confirm = args.get("requires_approval", False)

    if not cmd:
        return {"error": "[execute_command] 缺少 command 参数", "id": tool_call.get("id")}

    if need_confirm:
        # 非交互脚本中默认继续
        print(f"(auto-confirm) 将执行：{cmd}")

    extra_env: Optional[dict[str, str]] = None
    if env:
        # 使用传入的虚拟环境路径，如果没有则使用默认的base_dir/env
        if venv_path is None:
            venv_path = base_dir / "env"
        bin_dir = _prepare_venv(Path(venv_path))
        extra_env = {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
            "VIRTUAL_ENV": str(bin_dir.parent),
        }

    print(f"==> $ {cmd}")
    code, out, err = exec_shell(cmd, base_dir, extra_env=extra_env)

    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        print(err, file=sys.stderr)
    print(f"[exit {code}]")

    return {
        "id": tool_call.get("id"),
        "exit_code": code,
        "result": out + err,
    }


def handle_read_file(tool_call: Dict, base_dir: Path) -> Dict:
    args = json.loads(tool_call['function']['arguments'])
    path_text = args.get('path', '').strip()
    
    if not path_text:
        return {"id": tool_call.get("id"), "error": "[read_file] 缺少 path 参数"}

    path = _abs_path(path_text, base_dir)
    if not path.exists():
        return {"id": tool_call.get("id"), "error": f"文件不存在: {path}"}

    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            print(content)
            return {
                "id": tool_call.get("id"),
                "result": content
            }
    except Exception as e:
        return {"id": tool_call.get("id"), "error": f"读取文件失败: {e}"}


# chunk_list已移至utils.py


def handle_list_files(tool_call: Dict, base_dir: Path) -> Dict:
    args = json.loads(tool_call['function']['arguments'])
    path_text = args.get('path', '').strip()
    recursive = args.get('recursive', False)
    block = args.get('block', 1)

    if not path_text:
        return {"id": tool_call.get("id"), "error": "[list_files] 缺少 path 参数"}
    
    base = _abs_path(path_text, base_dir)

    if not base.exists():
        return {"id": tool_call.get("id"), "error": f"目录不存在: {base}"}

    # 收集条目
    items = []
    if recursive:
        for p in base.rglob("*"):
            items.append(str(p.relative_to(base_dir)))
    else:
        for p in base.iterdir():
            items.append(str(p.relative_to(base_dir)))

    cur, total, sub = chunk_list(sorted(items), block)
    output = f"当前块: {cur}/{total}\n"
    for x in sub:
        output += x + "\n"
        print(x)
    
    return {
        "id": tool_call.get("id"),
        "result": output.strip(),
        "current_block": cur,
        "total_blocks": total
    }


# apply_diff已移至diff_utils.py


def handle_replace_in_file(tool_call: Dict, base_dir: Path) -> Dict:
    args = json.loads(tool_call['function']['arguments'])
    path_text = args.get('path', '').strip()
    diff_text = args.get('diff', '')
    
    if not path_text or not diff_text.strip():
        return {"id": tool_call.get("id"), "error": "[replace_in_file] 缺少 path 或 diff 参数"}
    
    path = _abs_path(path_text, base_dir)
    if not path.exists():
        return {"id": tool_call.get("id"), "error": f"文件不存在: {path}"}

    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        out = apply_diff(src, diff_text)
        path.write_text(out, encoding="utf-8")
        result = f"{path} 已更新。"
        print(result)
        return {
            "id": tool_call.get("id"),
            "result": result
        }
    except Exception as e:
        return {"id": tool_call.get("id"), "error": f"替换失败: {e}"}


def handle_write_to_file(tool_call: Dict, base_dir: Path) -> Dict:
    """
    执行 write_to_file：
        • 自动创建缺失的父目录 & 文件
        • content 支持 <![CDATA[ ... ]]> 包裹
        • 返回统一结构：{ id, result } 或 { id, error }
    """
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except Exception as e:
        return {"id": tool_call.get("id"), "error": f"arguments 解析失败: {e}"}

    path_text = (args.get("path") or "").strip()
    content   = args.get("content", "")

    if not path_text:
        return {"id": tool_call.get("id"), "error": "[write_to_file] 缺少 path 参数"}

    # 若 content 形如 <![CDATA[ .... ]]> ，去掉最外层包裹
    cdata_match = re.fullmatch(r"<!\[CDATA\[(.*)\]\]>", content, re.S)
    if cdata_match:
        content = cdata_match.group(1)

    try:
        path = _abs_path(path_text, base_dir)
        path.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录
        # "w" 模式在文件不存在时会自动创建
        path.write_text(content, encoding="utf-8")
        result = f"{path} 写入完成 ({len(content)} bytes)"
        print(result)
        return {"id": tool_call.get("id"), "result": result}
    except Exception as e:
        return {"id": tool_call.get("id"), "error": f"写入文件失败: {e}"}



def regex_search_in_file(filepath: Path, pattern: re.Pattern, context: int = 2) -> List[str]:
    """在单个文件中搜索，返回含上下文的匹配行片段列表"""
    results = []
    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return results
    for idx, line in enumerate(lines, 1):
        if pattern.search(line):
            lo = max(0, idx - 1 - context)
            hi = min(len(lines), idx + context)
            snippet = "\n".join(f"{i+1:>5}: {lines[i]}" for i in range(lo, hi))
            results.append(f"{filepath}:\n{snippet}\n")
    return results


def handle_search_files(tool_call: Dict, base_dir: Path) -> Dict:
    args = json.loads(tool_call['function']['arguments'])
    path_text = args.get('path', '').strip()
    regex_text = args.get('regex', '')
    file_pattern = args.get('file_pattern', '')

    if not path_text or not regex_text:
        return {"id": tool_call.get("id"), "error": "[search_files] 缺少 path 或 regex 参数"}
    
    base = _abs_path(path_text, base_dir)
    try:
        pattern = re.compile(regex_text, re.MULTILINE)
    except re.error as e:
        return {"id": tool_call.get("id"), "error": f"正则表达式错误: {e}"}

    # 生成文件列表
    files: List[Path] = []
    if file_pattern:
        import glob
        files = [Path(p) for p in glob.glob(str(base / "**" / file_pattern), recursive=True)]
    else:
        files = [p for p in base.rglob("*") if p.is_file()]

    # 搜索
    output = ""
    for f in files:
        for snippet in regex_search_in_file(f, pattern):
            output += snippet + "\n"
            print(snippet)
    
    return {
        "id": tool_call.get("id"),
        "result": output.strip()
    }




# 工具处理映射
HANDLERS = {
    "execute_command": handle_execute,
    "read_file": handle_read_file,
    "list_files": handle_list_files,
    "replace_in_file": handle_replace_in_file,
    "write_to_file": handle_write_to_file,
    "search_files": handle_search_files,
}


def run_tool_calls(
    tool_calls: List[Dict],
    base_dir: Path,
    env: bool = False,
    venv_path: Optional[Path] = None,  # 新增：虚拟环境路径
) -> List[Dict]:
    """
    执行工具调用列表
    env=True 时，execute_command 会在指定的虚拟环境中运行
    其余工具不受影响
    """
    results: List[Dict] = []

    for tool_call in tool_calls:
        func_name = tool_call["function"]["name"]
        handler = HANDLERS.get(func_name)

        if handler is None:
            error_result = {
                "id": tool_call.get("id"),
                "error": f"未知工具: {func_name}",
            }
            results.append(error_result)
            print(error_result["error"], file=sys.stderr)
            continue

        print(f"\n--- 执行工具: {func_name} ---")
        try:
            # 仅 execute_command 透传 env 开关和虚拟环境路径
            if func_name == "execute_command":
                result = handler(tool_call, base_dir, env=env, venv_path=venv_path)
            else:
                result = handler(tool_call, base_dir)
            results.append(result)
        except Exception as exc:
            error_result = {
                "id": tool_call.get("id"),
                "error": f"处理 {func_name} 时发生错误: {exc}",
            }
            results.append(error_result)
            print(error_result["error"], file=sys.stderr)

    # 保持旧行为：只返回第一条结果；如需全部可改为 return results
    return results[0] if results else {}
