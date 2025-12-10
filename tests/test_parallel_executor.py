#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并行执行器单元测试
"""

import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.parallel_executor import ParallelExecutor, TaskQueue


class TestParallelExecutor:
    """并行执行器测试类"""
    
    def test_executor_initialization(self):
        """测试执行器初始化"""
        executor = ParallelExecutor(max_workers=4)
        assert executor.max_workers == 4
        assert executor.use_processes is False
    
    def test_run_tasks_parallel(self):
        """测试并行执行任务"""
        def simple_task(task, **kwargs):
            time.sleep(0.1)
            return {**task, 'pass': True, 'result': task['number'] * 2}
        
        tasks = [{'tag': 'test', 'number': i} for i in range(5)]
        
        executor = ParallelExecutor(max_workers=2)
        results = executor.run_tasks_parallel(tasks, simple_task)
        
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result['pass'] is True
    
    def test_error_handling(self):
        """测试错误处理"""
        def failing_task(task, **kwargs):
            if task['number'] % 2 == 0:
                raise ValueError("Test error")
            return {**task, 'pass': True}
        
        tasks = [{'tag': 'test', 'number': i} for i in range(4)]
        
        executor = ParallelExecutor(max_workers=2)
        results = executor.run_tasks_parallel(tasks, failing_task)
        
        assert len(results) == 4
        failed_count = sum(1 for r in results if not r.get('pass', False))
        assert failed_count == 2  # 偶数任务应该失败
    
    def test_safe_execute(self):
        """测试安全执行"""
        def task_with_exception(task, **kwargs):
            raise RuntimeError("Test exception")
        
        executor = ParallelExecutor(max_workers=1)
        result = executor._safe_execute(task_with_exception, {'tag': 'test', 'number': 1})
        
        assert result['pass'] is False
        assert 'error' in result
        assert result['error_type'] == 'RuntimeError'
    
    def test_batch_execution(self):
        """测试批量执行"""
        def simple_task(task, **kwargs):
            return {**task, 'pass': True}
        
        tasks = [{'tag': 'test', 'number': i} for i in range(10)]
        
        executor = ParallelExecutor(max_workers=2)
        results = executor.run_tasks_in_batches(tasks, simple_task, batch_size=3)
        
        assert len(results) == 10
        assert all(r['pass'] for r in results)


class TestTaskQueue:
    """任务队列测试类"""
    
    def test_queue_creation(self):
        """测试队列创建"""
        queue = TaskQueue(max_size=10)
        assert queue.size() == 0
        assert queue.is_empty() is True
    
    def test_add_and_get_tasks(self):
        """测试添加和获取任务"""
        queue = TaskQueue()
        
        # 添加任务
        task1 = {'id': 1, 'name': 'task1'}
        task2 = {'id': 2, 'name': 'task2'}
        
        assert queue.add_task(task1) is True
        assert queue.add_task(task2) is True
        assert queue.size() == 2
        
        # 获取任务
        tasks = queue.get_tasks(1)
        assert len(tasks) == 1
        assert tasks[0]['id'] == 1
        assert queue.size() == 1
        
        # 获取全部
        tasks = queue.get_tasks()
        assert len(tasks) == 1
        assert queue.is_empty() is True
    
    def test_max_size_limit(self):
        """测试队列大小限制"""
        queue = TaskQueue(max_size=2)
        
        assert queue.add_task({'id': 1}) is True
        assert queue.add_task({'id': 2}) is True
        assert queue.add_task({'id': 3}) is False  # 超过限制
        
        assert queue.size() == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
