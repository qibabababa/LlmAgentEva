#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块
收集和统计评测过程中的各种指标
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from threading import Lock

from lib.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class APICallMetric:
    """API调用指标"""
    timestamp: float
    model: str
    latency: float  # 秒
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    success: bool = True
    error: Optional[str] = None
    task_id: Optional[str] = None


@dataclass
class TaskMetric:
    """任务执行指标"""
    task_id: str
    task_type: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = False
    api_calls: int = 0
    tool_calls: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


class MetricsCollector:
    """指标收集器"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化指标收集器"""
        if not hasattr(self, '_initialized'):
            self.api_metrics: List[APICallMetric] = []
            self.task_metrics: List[TaskMetric] = []
            self.current_tasks: Dict[str, TaskMetric] = {}
            self._initialized = True
            logger.info("性能监控已初始化")
    
    def record_api_call(self,
                       model: str,
                       latency: float,
                       prompt_tokens: int = 0,
                       completion_tokens: int = 0,
                       success: bool = True,
                       error: Optional[str] = None,
                       task_id: Optional[str] = None):
        """
        记录API调用
        
        Args:
            model: 模型名称
            latency: 延迟（秒）
            prompt_tokens: 提示词token数
            completion_tokens: 完成token数
            success: 是否成功
            error: 错误信息
            task_id: 关联的任务ID
        """
        metric = APICallMetric(
            timestamp=time.time(),
            model=model,
            latency=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            success=success,
            error=error,
            task_id=task_id
        )
        
        with self._lock:
            self.api_metrics.append(metric)
            
            # 更新任务指标
            if task_id and task_id in self.current_tasks:
                self.current_tasks[task_id].api_calls += 1
                self.current_tasks[task_id].total_tokens += metric.total_tokens
        
        logger.debug(f"记录API调用: model={model}, latency={latency:.2f}s, tokens={metric.total_tokens}")
    
    def start_task(self, task_id: str, task_type: str):
        """
        开始任务计时
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
        """
        metric = TaskMetric(
            task_id=task_id,
            task_type=task_type,
            start_time=time.time()
        )
        
        with self._lock:
            self.current_tasks[task_id] = metric
        
        logger.debug(f"开始任务: {task_id} ({task_type})")
    
    def end_task(self, task_id: str, success: bool, error: Optional[str] = None):
        """
        结束任务计时
        
        Args:
            task_id: 任务ID
            success: 是否成功
            error: 错误信息
        """
        with self._lock:
            if task_id not in self.current_tasks:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            metric = self.current_tasks[task_id]
            metric.end_time = time.time()
            metric.duration = metric.end_time - metric.start_time
            metric.success = success
            metric.error = error
            
            # 移动到完成列表
            self.task_metrics.append(metric)
            del self.current_tasks[task_id]
        
        logger.debug(f"完成任务: {task_id}, 耗时={metric.duration:.2f}s, 成功={success}")
    
    def record_tool_call(self, task_id: str):
        """
        记录工具调用
        
        Args:
            task_id: 任务ID
        """
        with self._lock:
            if task_id in self.current_tasks:
                self.current_tasks[task_id].tool_calls += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取统计摘要
        
        Returns:
            统计数据字典
        """
        with self._lock:
            # API指标统计
            api_count = len(self.api_metrics)
            api_success_count = sum(1 for m in self.api_metrics if m.success)
            api_success_rate = api_success_count / api_count if api_count > 0 else 0
            
            total_latency = sum(m.latency for m in self.api_metrics)
            avg_latency = total_latency / api_count if api_count > 0 else 0
            
            total_tokens = sum(m.total_tokens for m in self.api_metrics)
            total_prompt_tokens = sum(m.prompt_tokens for m in self.api_metrics)
            total_completion_tokens = sum(m.completion_tokens for m in self.api_metrics)
            
            # 任务指标统计
            task_count = len(self.task_metrics)
            task_success_count = sum(1 for m in self.task_metrics if m.success)
            task_success_rate = task_success_count / task_count if task_count > 0 else 0
            
            total_duration = sum(m.duration for m in self.task_metrics if m.duration)
            avg_duration = total_duration / task_count if task_count > 0 else 0
            
            avg_tokens_per_task = total_tokens / task_count if task_count > 0 else 0
            
            # 按任务类型统计
            task_type_stats = {}
            for metric in self.task_metrics:
                task_type = metric.task_type
                if task_type not in task_type_stats:
                    task_type_stats[task_type] = {
                        'count': 0,
                        'success': 0,
                        'failed': 0,
                        'total_tokens': 0,
                        'avg_duration': 0
                    }
                
                task_type_stats[task_type]['count'] += 1
                if metric.success:
                    task_type_stats[task_type]['success'] += 1
                else:
                    task_type_stats[task_type]['failed'] += 1
                task_type_stats[task_type]['total_tokens'] += metric.total_tokens
                if metric.duration:
                    task_type_stats[task_type]['avg_duration'] += metric.duration
            
            # 计算平均值
            for task_type in task_type_stats:
                count = task_type_stats[task_type]['count']
                if count > 0:
                    task_type_stats[task_type]['avg_duration'] /= count
                    task_type_stats[task_type]['success_rate'] = \
                        task_type_stats[task_type]['success'] / count
            
            summary = {
                'timestamp': datetime.now().isoformat(),
                
                # API统计
                'api': {
                    'total_calls': api_count,
                    'success_calls': api_success_count,
                    'failed_calls': api_count - api_success_count,
                    'success_rate': api_success_rate,
                    'avg_latency': avg_latency,
                    'total_latency': total_latency,
                },
                
                # Token统计
                'tokens': {
                    'total': total_tokens,
                    'prompt': total_prompt_tokens,
                    'completion': total_completion_tokens,
                    'avg_per_task': avg_tokens_per_task,
                },
                
                # 任务统计
                'tasks': {
                    'total': task_count,
                    'success': task_success_count,
                    'failed': task_count - task_success_count,
                    'success_rate': task_success_rate,
                    'avg_duration': avg_duration,
                    'total_duration': total_duration,
                },
                
                # 按类型统计
                'by_task_type': task_type_stats,
            }
            
            return summary
    
    def export_to_json(self, output_file: Path):
        """
        导出指标到JSON文件
        
        Args:
            output_file: 输出文件路径
        """
        summary = self.get_summary()
        
        # 添加详细指标
        detailed = {
            'summary': summary,
            'api_calls': [asdict(m) for m in self.api_metrics],
            'tasks': [asdict(m) for m in self.task_metrics],
        }
        
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(detailed, f, ensure_ascii=False, indent=2)
        
        logger.info(f"性能指标已导出: {output_file}")
    
    def export_to_prometheus(self) -> str:
        """
        导出为Prometheus格式
        
        Returns:
            Prometheus格式的指标文本
        """
        summary = self.get_summary()
        
        lines = [
            "# HELP evaluation_api_calls_total Total number of API calls",
            "# TYPE evaluation_api_calls_total counter",
            f"evaluation_api_calls_total {summary['api']['total_calls']}",
            "",
            "# HELP evaluation_api_success_rate API call success rate",
            "# TYPE evaluation_api_success_rate gauge",
            f"evaluation_api_success_rate {summary['api']['success_rate']:.4f}",
            "",
            "# HELP evaluation_api_latency_seconds Average API latency in seconds",
            "# TYPE evaluation_api_latency_seconds gauge",
            f"evaluation_api_latency_seconds {summary['api']['avg_latency']:.4f}",
            "",
            "# HELP evaluation_tokens_total Total tokens used",
            "# TYPE evaluation_tokens_total counter",
            f"evaluation_tokens_total {summary['tokens']['total']}",
            "",
            "# HELP evaluation_tasks_total Total number of tasks",
            "# TYPE evaluation_tasks_total counter",
            f"evaluation_tasks_total {summary['tasks']['total']}",
            "",
            "# HELP evaluation_task_success_rate Task success rate",
            "# TYPE evaluation_task_success_rate gauge",
            f"evaluation_task_success_rate {summary['tasks']['success_rate']:.4f}",
            "",
        ]
        
        return "\n".join(lines)
    
    def print_summary(self):
        """打印统计摘要"""
        summary = self.get_summary()
        
        print("\n" + "=" * 70)
        print("📊 性能统计")
        print("=" * 70)
        
        # API统计
        api = summary['api']
        print(f"\nAPI调用:")
        print(f"  总调用次数: {api['total_calls']}")
        print(f"  成功: {api['success_calls']}")
        print(f"  失败: {api['failed_calls']}")
        print(f"  成功率: {api['success_rate']:.1%}")
        print(f"  平均延迟: {api['avg_latency']:.2f}秒")
        print(f"  总耗时: {api['total_latency']:.2f}秒")
        
        # Token统计
        tokens = summary['tokens']
        print(f"\nToken使用:")
        print(f"  总Token: {tokens['total']:,}")
        print(f"  提示词Token: {tokens['prompt']:,}")
        print(f"  完成Token: {tokens['completion']:,}")
        print(f"  平均Token/任务: {tokens['avg_per_task']:.0f}")
        
        # 任务统计
        tasks = summary['tasks']
        print(f"\n任务执行:")
        print(f"  总任务数: {tasks['total']}")
        print(f"  成功: {tasks['success']}")
        print(f"  失败: {tasks['failed']}")
        print(f"  成功率: {tasks['success_rate']:.1%}")
        print(f"  平均耗时: {tasks['avg_duration']:.2f}秒")
        print(f"  总耗时: {tasks['total_duration']:.2f}秒")
        
        # 按任务类型统计
        if summary['by_task_type']:
            print(f"\n按任务类型:")
            for task_type, stats in summary['by_task_type'].items():
                print(f"  {task_type}:")
                print(f"    数量: {stats['count']}")
                print(f"    成功率: {stats['success_rate']:.1%}")
                print(f"    平均耗时: {stats['avg_duration']:.2f}秒")
                print(f"    Token使用: {stats['total_tokens']:,}")
        
        print("=" * 70 + "\n")
    
    def reset(self):
        """重置所有指标"""
        with self._lock:
            self.api_metrics.clear()
            self.task_metrics.clear()
            self.current_tasks.clear()
        
        logger.info("性能指标已重置")


# 全局单例
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


if __name__ == "__main__":
    # 测试
    collector = MetricsCollector()
    
    # 模拟任务
    collector.start_task("task_1", "fix_bug")
    collector.record_api_call("qwen3-235b", 2.5, 100, 50, True, task_id="task_1")
    time.sleep(0.1)
    collector.record_api_call("qwen3-235b", 1.8, 80, 40, True, task_id="task_1")
    collector.record_tool_call("task_1")
    collector.end_task("task_1", True)
    
    collector.start_task("task_2", "convert")
    collector.record_api_call("qwen3-235b", 3.0, 120, 60, False, "Timeout", task_id="task_2")
    collector.end_task("task_2", False, "API failed")
    
    # 打印摘要
    collector.print_summary()
    
    # 导出
    collector.export_to_json(Path("test_metrics.json"))
    print("\n✅ 测试完成")
