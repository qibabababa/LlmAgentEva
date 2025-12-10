#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块单元测试
"""

import sys
import pytest
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.metrics import MetricsCollector, APICallMetric, TaskMetric


class TestMetricsCollector:
    """性能监控测试类"""
    
    @pytest.fixture
    def collector(self):
        """创建测试用的指标收集器"""
        collector = MetricsCollector()
        collector.reset()  # 重置状态
        return collector
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        collector1 = MetricsCollector()
        collector2 = MetricsCollector()
        assert collector1 is collector2, "MetricsCollector应该是单例"
    
    def test_record_api_call(self, collector):
        """测试记录API调用"""
        collector.record_api_call(
            model="test-model",
            latency=2.5,
            prompt_tokens=100,
            completion_tokens=50,
            success=True
        )
        
        assert len(collector.api_metrics) == 1
        metric = collector.api_metrics[0]
        assert metric.model == "test-model"
        assert metric.latency == 2.5
        assert metric.prompt_tokens == 100
        assert metric.completion_tokens == 50
        assert metric.total_tokens == 150
        assert metric.success is True
    
    def test_task_lifecycle(self, collector):
        """测试任务生命周期"""
        # 开始任务
        collector.start_task("task_1", "fix_bug")
        assert "task_1" in collector.current_tasks
        
        # 记录API调用
        collector.record_api_call(
            model="test-model",
            latency=1.0,
            prompt_tokens=50,
            completion_tokens=25,
            task_id="task_1"
        )
        
        # 验证任务指标更新
        task_metric = collector.current_tasks["task_1"]
        assert task_metric.api_calls == 1
        assert task_metric.total_tokens == 75
        
        # 结束任务
        collector.end_task("task_1", success=True)
        assert "task_1" not in collector.current_tasks
        assert len(collector.task_metrics) == 1
        
        completed_task = collector.task_metrics[0]
        assert completed_task.task_id == "task_1"
        assert completed_task.success is True
        assert completed_task.duration is not None
    
    def test_tool_call_recording(self, collector):
        """测试工具调用记录"""
        collector.start_task("task_1", "fix_bug")
        
        collector.record_tool_call("task_1")
        collector.record_tool_call("task_1")
        
        task_metric = collector.current_tasks["task_1"]
        assert task_metric.tool_calls == 2
    
    def test_get_summary(self, collector):
        """测试获取统计摘要"""
        # 记录一些数据
        collector.start_task("task_1", "fix_bug")
        collector.record_api_call(
            model="test-model",
            latency=2.0,
            prompt_tokens=100,
            completion_tokens=50,
            success=True,
            task_id="task_1"
        )
        collector.end_task("task_1", success=True)
        
        collector.start_task("task_2", "convert")
        collector.record_api_call(
            model="test-model",
            latency=3.0,
            prompt_tokens=150,
            completion_tokens=75,
            success=False,
            error="Timeout",
            task_id="task_2"
        )
        collector.end_task("task_2", success=False, error="API failed")
        
        # 获取摘要
        summary = collector.get_summary()
        
        # 验证API统计
        assert summary['api']['total_calls'] == 2
        assert summary['api']['success_calls'] == 1
        assert summary['api']['failed_calls'] == 1
        assert summary['api']['success_rate'] == 0.5
        assert summary['api']['avg_latency'] == 2.5
        
        # 验证Token统计
        assert summary['tokens']['total'] == 375
        assert summary['tokens']['prompt'] == 250
        assert summary['tokens']['completion'] == 125
        
        # 验证任务统计
        assert summary['tasks']['total'] == 2
        assert summary['tasks']['success'] == 1
        assert summary['tasks']['failed'] == 1
        assert summary['tasks']['success_rate'] == 0.5
        
        # 验证按类型统计
        assert 'fix_bug' in summary['by_task_type']
        assert 'convert' in summary['by_task_type']
        assert summary['by_task_type']['fix_bug']['count'] == 1
        assert summary['by_task_type']['fix_bug']['success'] == 1
    
    def test_export_to_json(self, collector, tmp_path):
        """测试导出为JSON"""
        collector.start_task("task_1", "fix_bug")
        collector.record_api_call(
            model="test-model",
            latency=1.5,
            prompt_tokens=80,
            completion_tokens=40,
            task_id="task_1"
        )
        collector.end_task("task_1", success=True)
        
        # 导出
        output_file = tmp_path / "metrics.json"
        collector.export_to_json(output_file)
        
        # 验证文件存在
        assert output_file.exists()
        
        # 读取并验证内容
        import json
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert 'summary' in data
        assert 'api_calls' in data
        assert 'tasks' in data
        assert len(data['api_calls']) == 1
        assert len(data['tasks']) == 1
    
    def test_reset(self, collector):
        """测试重置"""
        collector.start_task("task_1", "fix_bug")
        collector.record_api_call(model="test-model", latency=1.0)
        
        collector.reset()
        
        assert len(collector.api_metrics) == 0
        assert len(collector.task_metrics) == 0
        assert len(collector.current_tasks) == 0
    
    def test_concurrent_access(self, collector):
        """测试并发访问"""
        import threading
        
        def add_metrics():
            for i in range(10):
                collector.record_api_call(
                    model="test-model",
                    latency=1.0,
                    prompt_tokens=100,
                    completion_tokens=50
                )
        
        # 创建多个线程
        threads = [threading.Thread(target=add_metrics) for _ in range(5)]
        
        # 启动所有线程
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有指标都被记录
        assert len(collector.api_metrics) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
