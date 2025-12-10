import ast
import subprocess
import sys
from pathlib import Path
from typing import Dict, Set, List

from lib.core.logger import get_logger

# 创建logger
logger = get_logger(__name__)


def _execute_python_file(file_path: Path) -> str:
    """运行脚本并返回 stdout（失败抛异常）。"""
    proc = subprocess.run(
        [sys.executable, str(file_path)],
        text=True,
        check=True,
        capture_output=True
    )
    return proc.stdout


def _collect_defined_names(src: str) -> Set[str]:
    """AST 遍历，收集:
        1. 顶级函数/类名
        2. 类的方法名
        3. 顶层变量名（普通赋值、类型注解赋值、增量赋值）
    """
    tree = ast.parse(src)
    names: Set[str] = set()

    # ---- 递归提取 Assign 目标中的变量名 ----
    def _extract_target_names(target) -> List[str]:
        """从各种赋值 target 中提取变量标识符"""
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            acc = []
            for elt in target.elts:
                acc.extend(_extract_target_names(elt))
            return acc
        # 忽略 Attribute / Subscript 等更深层次的情况
        return []

    class Collector(ast.NodeVisitor):
        # 1. 函数定义
        def visit_FunctionDef(self, node):
            names.add(node.name)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            names.add(node.name)
            self.generic_visit(node)

        # 2. 类定义 及其方法
        def visit_ClassDef(self, node):
            names.add(node.name)
            for n in node.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(n.name)
            self.generic_visit(node)

        # 3. 顶层变量定义
        def visit_Assign(self, node):
            # 只统计顶层：node.parent 在 Python AST 默认没有，
            # 利用当前遍历深度，通过 hasattr(node, 'parent') 或者
            # 判断 self.stack 长度也可以。为了简单，这里直接判断
            # 若当前赋值节点位于 Module.body，则收集:
            if isinstance(getattr(node, 'parent', None), ast.Module):
                for tgt in node.targets:
                    names.update(_extract_target_names(tgt))
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            if isinstance(getattr(node, 'parent', None), ast.Module):
                names.update(_extract_target_names(node.target))
            self.generic_visit(node)

        def visit_AugAssign(self, node):
            if isinstance(getattr(node, 'parent', None), ast.Module):
                names.update(_extract_target_names(node.target))
            self.generic_visit(node)

        # ---------- 重写 generic_visit 以写入 parent ----------
        def generic_visit(self, node):
            for child in ast.iter_child_nodes(node):
                setattr(child, 'parent', node)
                self.visit(child)

    Collector().visit(tree)
    return names


def validate_refactor(
        file_path: str,
        rename_map: Dict[str, str],
        expected_output_file: str | None = None,
        run_script: bool = True
) -> bool:
    """
    验证重构任务是否完成
    
    Args:
        file_path: 被重构的文件路径
        rename_map: 重命名映射 {旧名称: 新名称}
        expected_output_file: 期望输出文件路径（可选）
        run_script: 是否运行脚本验证
    
    Returns:
        是否通过验证
        
    验证逻辑：
        1. 检查旧名称是否已全部移除
        2. 检查新名称是否都存在
        3. 运行脚本验证功能正确性
        4. 对比输出与原始输出一致
    """
    new_path = Path(file_path)
    if not new_path.exists():
        logger.error(f"找不到文件: {file_path}")
        return False

    # 读取文件内容
    try:
        src = new_path.read_text(encoding="utf-8")
        logger.debug(f"成功读取文件: {file_path}, 大小: {len(src)} bytes")
    except Exception as e:
        logger.error(f"无法读取文件: {e}")
        return False

    # 收集定义的名称
    try:
        defined_names = _collect_defined_names(src)
        logger.debug(f"收集到 {len(defined_names)} 个定义的名称: {defined_names}")
    except Exception as e:
        logger.error(f"解析AST失败: {e}")
        return False

    # 1. 命名检查
    logger.info(f"开始检查重命名映射 (共 {len(rename_map)} 个)")
    for old_name, new_name in rename_map.items():
        if old_name in defined_names:
            logger.error(f"重构失败: 脚本仍然定义旧名称: {old_name}")
            return False
        if new_name not in defined_names:
            logger.error(f"重构失败: 未找到新名称定义: {new_name}")
            return False
        logger.info(f"  ✓ 重命名成功: {old_name} → {new_name}")

    # 2. 运行脚本并对比输出
    if run_script:
        logger.info("运行脚本验证功能...")
        try:
            actual_stdout = _execute_python_file(new_path)
            logger.info("脚本运行成功")
            logger.debug(f"脚本输出: {actual_stdout[:200]}...")
        except subprocess.CalledProcessError as exc:
            logger.error(f"脚本运行失败, 返回码: {exc.returncode}")
            logger.error(f"  stdout: {exc.stdout}")
            logger.error(f"  stderr: {exc.stderr}")
            return False
        except Exception as e:
            logger.error(f"运行脚本时出错: {e}")
            return False
        
        # 3. 对比输出
        if expected_output_file:
            expected_path = Path(expected_output_file)
            if not expected_path.exists():
                logger.warning(f"期望输出文件不存在: {expected_output_file}, 跳过输出对比")
            else:
                try:
                    expected_stdout = expected_path.read_text(encoding="utf-8")
                    if actual_stdout != expected_stdout:
                        logger.error("运行输出与预期不一致")
                        logger.debug(f"期望输出:\n{expected_stdout}")
                        logger.debug(f"实际输出:\n{actual_stdout}")
                        return False
                    logger.info("输出与期望一致")
                except Exception as e:
                    logger.error(f"读取期望输出失败: {e}")
                    return False

    logger.info("重构验证通过")
    return True


# ----------------------- 使用示例 -----------------------
if __name__ == "__main__":
    # 测试refactor验证
    rename_dict = {
        "add_two_numbers": "addTwoNumbers",
        "multiply_two_numbers": "multiplyTwoNumbers",
        "process_user_input": "processUserInput"
    }

    ok = validate_refactor(
        file_path="data/tasks/code_refactor/utils.py",
        rename_map=rename_dict,
        expected_output_file="data/tasks/code_refactor/expected_output.txt",
        run_script=True
    )
    
    print(f"\n{'='*50}")
    print(f"验证结果: {'通过 ✅' if ok else '失败 ❌'}")
    print(f"{'='*50}")
    
    sys.exit(0 if ok else 1)
