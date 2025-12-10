#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行执行器
支持多任务并行评测
"""

import time
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from threading import Lock

from lib.core.logger import get_logger
from lib.core.metrics import get_metrics_collector

logger = get_logger(__name__)


class ParallelExecutor:
    """并行执行器"""
    
    def __init__(self, max_workers: int = 4, use_processes: bool = False):
        """
        初始化并行执行器
        
        Args:
            max_workers: 最大并行任务数
            use_processes: 是否使用进程池（默认使用线程池）
        """
        self.max_workers = max_workers
        self.use_processes = use_processes
        self._lock = Lock()
        self.metrics = get_metrics_collector()
        
        logger.info(f"并行执行器已初始化: max_workers={max_workers}, use_processes={use_processes}")
    
    def run_tasks_parallel(self,
                          tasks: List[Dict[str, Any]],
                          executor_func: Callable,
                          **kwargs) -> List[Dict[str, Any]]:
        """
        并行执行多个任务
        
        Args:
            tasks: 任务列表
            executor_func: 执行函数，接收task和**kwargs
            **kwargs: 传递给executor_func的额外参数
            
        Returns:
            执行结果列表
        """
        logger.info(f"开始并行执行 {len(tasks)} 个任务，并行度={self.max_workers}")
        
        results = []
        completed_count = 0
        failed_count = 0
        
        # 选择执行器类型
        ExecutorClass = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor
        
        start_time = time.time()
        
        with ExecutorClass(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            for task in tasks:
                future = executor.submit(self._safe_execute, executor_func, task, **kwargs)
                future_to_task[future] = task
            
            # 处理完成的任务
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                task_id = f"{task.get('tag', 'unknown')}_{task.get('number', 'N/A')}"
                
                try:
                    result = future.result()
                    
                    with self._lock:
                        results.append(result)
                        completed_count += 1
                        
                        if result.get('pass', False):
                            status = "✅"
                        else:
                            status = "❌"
                            failed_count += 1
                        
                        progress = completed_count / len(tasks) * 100
                        logger.info(
                            f"{status} [{completed_count}/{len(tasks)}] ({progress:.1f}%) "
                            f"任务完成: {task_id}"
                        )
                        print(f"{status} [{completed_count}/{len(tasks)}] {task_id}")
                
                except Exception as e:
                    logger.error(f"任务执行异常: {task_id} - {e}")
                    
                    with self._lock:
                        failed_count += 1
                        completed_count += 1
                        results.append({
                            **task,
                            'pass': False,
                            'error': str(e),
                            'error_type': type(e).__name__
                        })
        
        elapsed = time.time() - start_time
        
        logger.info(
            f"并行执行完成: 总数={len(tasks)}, 成功={completed_count - failed_count}, "
            f"失败={failed_count}, 耗时={elapsed:.2f}秒"
        )
        
        return results
    
    def _safe_execute(self, func: Callable, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        安全执行单个任务（带错误处理）
        
        Args:
            func: 执行函数
            task: 任务数据
            **kwargs: 额外参数
            
        Returns:
            执行结果
        """
        task_id = f"{task.get('tag', 'unknown')}_{task.get('number', 'N/A')}"
        
        try:
            # 开始任务监控
            self.metrics.start_task(task_id, task.get('tag', 'unknown'))
            
            # 执行任务
            result = func(task, **kwargs)
            
            # 结束任务监控
            self.metrics.end_task(task_id, result.get('pass', False))
            
            return result
            
        except Exception as e:
            logger.error(f"任务执行失败: {task_id} - {e}")
            
            # 记录失败
            self.metrics.end_task(task_id, False, str(e))
            
            return {
                **task,
                'pass': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def run_tasks_in_batches(self,
                            tasks: List[Dict[str, Any]],
                            executor_func: Callable,
                            batch_size: Optional[int] = None,
                            **kwargs) -> List[Dict[str, Any]]:
        """
        批量并行执行任务
        
        Args:
            tasks: 任务列表
            executor_func: 执行函数
            batch_size: 批次大小（默认为max_workers * 2）
            **kwargs: 额外参数
            
        Returns:
            执行结果列表
        """
        if batch_size is None:
            batch_size = self.max_workers * 2
        
        logger.info(f"批量执行 {len(tasks)} 个任务，批次大小={batch_size}")
        
        all_results = []
        
        # 分批执行
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(tasks) + batch_size - 1) // batch_size
            
            logger.info(f"执行批次 {batch_num}/{total_batches} ({len(batch)} 个任务)")
            
            batch_results = self.run_tasks_parallel(batch, executor_func, **kwargs)
            all_results.extend(batch_results)
        
        return all_results


class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self, max_size: Optional[int] = None):
        """
        初始化任务队列
        
        Args:
            max_size: 最大队列长度
        """
        self.tasks = []
        self.max_size = max_size
        self._lock = Lock()
        logger.info(f"任务队列已创建: max_size={max_size}")
    
    def add_task(self, task: Dict[str, Any]) -> bool:
        """
        添加任务到队列
        
        Args:
            task: 任务数据
            
        Returns:
            是否添加成功
        """
        with self._lock:
            if self.max_size and len(self.tasks) >= self.max_size:
                logger.warning("任务队列已满")
                return False
            
            self.tasks.append(task)
            logger.debug(f"任务已添加: {task.get('tag')}_{task.get('number')}")
            return True
    
    def get_tasks(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取任务
        
        Args:
            count: 获取数量（None表示全部）
            
        Returns:
            任务列表
        """
        with self._lock:
            if count is None:
                tasks = self.tasks.copy()
                self.tasks.clear()
            else:
                tasks = self.tasks[:count]
                self.tasks = self.tasks[count:]
            
            return tasks
    
    def size(self) -> int:
        """获取队列长度"""
        with self._lock:
            return len(self.tasks)
    
    def is_empty(self) -> bool:
        """队列是否为空"""
        return self.size() == 0


def create_parallel_executor(max_workers: int = 4, 
                             use_processes: bool = False) -> ParallelExecutor:
    """
    创建并行执行器
    
    Args:
        max_workers: 最大并行任务数
        use_processes: 是否使用进程池
        
    Returns:
        并行执行器实例
    """
    return ParallelExecutor(max_workers=max_workers, use_processes=use_processes)


if __name__ == "__main__":
    # 测试
    import random
    
    def mock_task(task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """模拟任务执行"""
        task_id = f"{task['tag']}_{task['number']}"
        
        # 模拟耗时
        time.sleep(random.uniform(0.1, 0.5))
        
        # 模拟成功/失败
        success = random.random() > 0.2
        
        result = {
            **task,
            'pass': success,
        }
        
        if not success:
            result['error'] = "模拟错误"
        
        return result
    
    # 创建测试任务
    test_tasks = [
        {'tag': 'fix_bug', 'number': i} 
        for i in range(10)
    ]
    
    # 创建执行器
    executor = ParallelExecutor(max_workers=4)
    
    # 并行执行
    print(f"\n开始并行执行 {len(test_tasks)} 个任务...\n")
    results = executor.run_tasks_parallel(test_tasks, mock_task)
    
    # 统计结果
    passed = sum(1 for r in results if r.get('pass'))
    print(f"\n执行完成: 成功={passed}/{len(results)}")
