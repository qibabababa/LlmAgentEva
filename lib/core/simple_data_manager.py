#!/usr/bin/env python3
"""
简单数据管理器 - 只负责tasks目录的自动备份恢复
不修改原始测试集格式，完全保持兼容
"""

import shutil
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from lib.core.logger import get_logger

logger = get_logger(__name__)


class SimpleDataManager:
    """
    简单数据管理器
    
    功能：
    1. 自动备份tasks目录（评测前）
    2. 自动恢复tasks目录（评测后）
    3. 不修改原始测试集JSON格式
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """初始化"""
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent
        
        self.project_root = Path(project_root)
        self.tasks_dir = self.project_root / "data" / "tasks"
        self.backup_dir = self.project_root / "data" / ".tasks_backup"
        
        logger.debug(f"SimpleDataManager初始化: tasks={self.tasks_dir}")
    
    def create_backup(self) -> bool:
        """创建tasks目录备份"""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            
            shutil.copytree(self.tasks_dir, self.backup_dir)
            logger.info(f"已备份tasks目录")
            return True
            
        except Exception as e:
            logger.error(f"备份失败: {e}")
            return False
    
    def restore_from_backup(self) -> bool:
        """从备份恢复tasks目录"""
        try:
            if not self.backup_dir.exists():
                logger.warning("备份不存在，无法恢复")
                return False
            
            if self.tasks_dir.exists():
                shutil.rmtree(self.tasks_dir)
            
            shutil.copytree(self.backup_dir, self.tasks_dir)
            logger.info(f"已恢复tasks目录")
            return True
            
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return False
    
    def cleanup_backup(self):
        """清理备份"""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
                logger.debug("已清理备份")
        except Exception as e:
            logger.warning(f"清理备份失败: {e}")
    
    @contextmanager
    def auto_restore_tasks(self):
        """
        上下文管理器：自动备份和恢复tasks目录
        
        恢复是强制的，不可跳过。如果备份失败，评测不会执行。
        
        使用示例:
            with data_manager.auto_restore_tasks():
                run_evaluation()  # 可能修改tasks目录
            # 退出时必定恢复
        """
        logger.info("开始自动备份恢复流程")
        
        # 备份（必须成功）
        backup_success = self.create_backup()
        if not backup_success:
            error_msg = "备份失败，无法保证数据恢复，评测终止"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            yield
        finally:
            # 强制恢复（不论评测成功或失败）
            logger.info("开始强制恢复数据...")
            restore_success = self.restore_from_backup()
            
            if not restore_success:
                # 恢复失败是严重错误
                logger.critical("❌ 数据恢复失败！tasks目录可能已被修改！")
                logger.critical(f"请手动检查备份: {self.backup_dir}")
                raise RuntimeError("数据恢复失败，请手动恢复数据")
            
            # 清理备份
            self.cleanup_backup()
            logger.info("✅ 数据恢复完成")


# 全局实例
_manager = None

def get_simple_data_manager() -> SimpleDataManager:
    """获取全局数据管理器实例"""
    global _manager
    if _manager is None:
        _manager = SimpleDataManager()
    return _manager


if __name__ == "__main__":
    # 测试
    manager = SimpleDataManager()
    
    print("测试备份...")
    success = manager.create_backup()
    print(f"备份结果: {'成功' if success else '失败'}")
    
    print("\n测试恢复...")
    success = manager.restore_from_backup()
    print(f"恢复结果: {'成功' if success else '失败'}")
    
    print("\n测试清理...")
    manager.cleanup_backup()
    print("清理完成")
