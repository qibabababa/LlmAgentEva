#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评测报告生成器
支持HTML和Markdown格式
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from lib.core.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """评测报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_html_report(self, stats: Dict[str, Any], output_file: Path) -> Path:
        """
        生成HTML格式的评测报告
        
        Args:
            stats: 统计数据
            output_file: 输出文件路径
            
        Returns:
            生成的报告文件路径
        """
        logger.info(f"开始生成HTML报告: {output_file}")
        
        # 提取数据
        total = stats.get('total', 0)
        passed = stats.get('passed', 0)
        failed = stats.get('failed', 0)
        pass_rate = stats.get('pass_rate', 0)
        results = stats.get('results', [])
        
        # 新增的详细统计
        tool_stats = stats.get('tool_stats', {})
        round_stats = stats.get('round_stats', {})
        output_stats = stats.get('output_stats', {})
        error_stats = stats.get('error_stats', {})
        by_task_type = stats.get('by_task_type', {})
        
        # 兼容旧的metrics字段
        metrics = stats.get('metrics', {})
        
        # 生成HTML
        html = self._generate_html_template(
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            task_stats=by_task_type,  # 使用新的按类型统计
            results=results,
            metrics=metrics,
            tool_stats=tool_stats,
            round_stats=round_stats,
            output_stats=output_stats,
            error_stats=error_stats
        )
        
        # 写入文件
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"HTML报告已生成: {output_file}")
        return output_file
    
    def generate_markdown_report(self, stats: Dict[str, Any], output_file: Path) -> Path:
        """
        生成Markdown格式的评测报告
        
        Args:
            stats: 统计数据
            output_file: 输出文件路径
            
        Returns:
            生成的报告文件路径
        """
        logger.info(f"开始生成Markdown报告: {output_file}")
        
        # 提取数据
        total = stats.get('total', 0)
        passed = stats.get('passed', 0)
        failed = stats.get('failed', 0)
        pass_rate = stats.get('pass_rate', 0)
        results = stats.get('results', [])
        metrics = stats.get('metrics', {})
        
        # 按任务类型分组
        task_stats = self._group_by_task_type(results)
        
        # 生成Markdown
        md = self._generate_markdown_template(
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            task_stats=task_stats,
            results=results,
            metrics=metrics
        )
        
        # 写入文件
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md)
        
        logger.info(f"Markdown报告已生成: {output_file}")
        return output_file
    
    def _group_by_task_type(self, results: List[Dict]) -> Dict[str, Dict]:
        """按任务类型分组统计"""
        task_stats = {}
        
        for result in results:
            task_type = result.get('tag', 'unknown')
            
            if task_type not in task_stats:
                task_stats[task_type] = {
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'pass_rate': 0
                }
            
            task_stats[task_type]['total'] += 1
            if result.get('pass', False):
                task_stats[task_type]['passed'] += 1
            else:
                task_stats[task_type]['failed'] += 1
        
        # 计算通过率
        for task_type in task_stats:
            total = task_stats[task_type]['total']
            passed = task_stats[task_type]['passed']
            task_stats[task_type]['pass_rate'] = passed / total if total > 0 else 0
        
        return task_stats
    
    def _generate_html_template(self, **kwargs) -> str:
        """生成HTML模板"""
        total = kwargs['total']
        passed = kwargs['passed']
        failed = kwargs['failed']
        pass_rate = kwargs['pass_rate']
        task_stats = kwargs['task_stats']
        results = kwargs['results']
        metrics = kwargs.get('metrics', {})
        
        # 任务类型统计表格
        task_table_rows = ""
        for task_type, stats in sorted(task_stats.items()):
            rate = stats['pass_rate']
            rate_color = self._get_rate_color(rate)
            task_table_rows += f"""
                <tr>
                    <td>{task_type}</td>
                    <td>{stats['total']}</td>
                    <td style="color: #28a745;">{stats['passed']}</td>
                    <td style="color: #dc3545;">{stats['failed']}</td>
                    <td style="color: {rate_color}; font-weight: bold;">{rate:.1%}</td>
                </tr>
            """
        
        # 失败案例详情
        failed_cases = ""
        for idx, result in enumerate(results, 1):
            if not result.get('pass', False):
                error = result.get('error', '未知错误')
                error_type = result.get('error_type', '未知')
                fail_step = result.get('fail_step', '未知')
                
                failed_cases += f"""
                    <div class="failed-case">
                        <h4>❌ 案例 {idx}: {result.get('tag', 'unknown')} - {result.get('number', 'N/A')}</h4>
                        <p><strong>失败步骤:</strong> {fail_step}</p>
                        <p><strong>错误类型:</strong> {error_type}</p>
                        <p><strong>错误信息:</strong></p>
                        <pre>{error}</pre>
                    </div>
                """
        
        if not failed_cases:
            failed_cases = "<p style='color: #28a745;'>🎉 所有测试都通过了！</p>"
        
        # 性能指标
        metrics_html = ""
        if metrics:
            avg_latency = metrics.get('avg_api_latency', 0)
            total_tokens = metrics.get('total_tokens', 0)
            avg_tokens = metrics.get('avg_tokens_per_task', 0)
            
            metrics_html = f"""
                <div class="metrics-section">
                    <h3>📊 性能指标</h3>
                    <div class="metric-card">
                        <div class="metric-label">平均API延迟</div>
                        <div class="metric-value">{avg_latency:.2f}秒</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">总Token使用量</div>
                        <div class="metric-value">{total_tokens:,}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">平均Token/任务</div>
                        <div class="metric-value">{avg_tokens:.0f}</div>
                    </div>
                </div>
            """
        
        # 完整HTML
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>评测报告 - {self.timestamp}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 40px;
            background: #f8f9fa;
        }}
        
        .summary-card {{
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.2s;
        }}
        
        .summary-card:hover {{
            transform: translateY(-5px);
        }}
        
        .summary-card .label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .summary-card .value {{
            font-size: 2.5em;
            font-weight: bold;
        }}
        
        .summary-card.pass .value {{
            color: #28a745;
        }}
        
        .summary-card.fail .value {{
            color: #dc3545;
        }}
        
        .summary-card.rate .value {{
            color: {self._get_rate_color(pass_rate)};
        }}
        
        .content {{
            padding: 40px;
        }}
        
        h2 {{
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        h3 {{
            color: #764ba2;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .failed-case {{
            background: #fff5f5;
            border-left: 4px solid #dc3545;
            padding: 20px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        
        .failed-case h4 {{
            color: #dc3545;
            margin-bottom: 10px;
        }}
        
        .failed-case pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.9em;
            margin-top: 10px;
        }}
        
        .metrics-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            text-align: center;
        }}
        
        .metric-label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 10px;
        }}
        
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #28a745, #20c997);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            transition: width 1s ease;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🎯 评测报告</h1>
            <p>生成时间: {self.timestamp}</p>
        </div>
        
        <!-- Summary Cards -->
        <div class="summary">
            <div class="summary-card">
                <div class="label">总任务数</div>
                <div class="value">{total}</div>
            </div>
            <div class="summary-card pass">
                <div class="label">✅ 通过</div>
                <div class="value">{passed}</div>
            </div>
            <div class="summary-card fail">
                <div class="label">❌ 失败</div>
                <div class="value">{failed}</div>
            </div>
            <div class="summary-card rate">
                <div class="label">通过率</div>
                <div class="value">{pass_rate:.1%}</div>
            </div>
        </div>
        
        <!-- Progress Bar -->
        <div style="padding: 0 40px;">
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_rate * 100}%">
                    {pass_rate:.1%}
                </div>
            </div>
        </div>
        
        <!-- Content -->
        <div class="content">
            <!-- Task Type Statistics -->
            <h2>📋 任务类型统计</h2>
            <table>
                <thead>
                    <tr>
                        <th>任务类型</th>
                        <th>总数</th>
                        <th>通过</th>
                        <th>失败</th>
                        <th>通过率</th>
                    </tr>
                </thead>
                <tbody>
                    {task_table_rows}
                </tbody>
            </table>
            
            <!-- Performance Metrics -->
            {metrics_html}
            
            <!-- Failed Cases -->
            <h2>❌ 失败案例详情</h2>
            {failed_cases}
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p>Docker Build Evaluation System v2.0</p>
            <p>© 2024 - Powered by AI</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _generate_markdown_template(self, **kwargs) -> str:
        """生成Markdown模板"""
        total = kwargs['total']
        passed = kwargs['passed']
        failed = kwargs['failed']
        pass_rate = kwargs['pass_rate']
        task_stats = kwargs['task_stats']
        results = kwargs['results']
        metrics = kwargs.get('metrics', {})
        
        # 任务类型统计表格
        task_table = "| 任务类型 | 总数 | 通过 | 失败 | 通过率 |\n"
        task_table += "|---------|------|------|------|--------|\n"
        for task_type, stats in sorted(task_stats.items()):
            task_table += f"| {task_type} | {stats['total']} | {stats['passed']} | {stats['failed']} | {stats['pass_rate']:.1%} |\n"
        
        # 失败案例
        failed_cases = ""
        for idx, result in enumerate(results, 1):
            if not result.get('pass', False):
                error = result.get('error', '未知错误')
                error_type = result.get('error_type', '未知')
                fail_step = result.get('fail_step', '未知')
                
                failed_cases += f"""
### ❌ 案例 {idx}: {result.get('tag', 'unknown')} - {result.get('number', 'N/A')}

- **失败步骤**: {fail_step}
- **错误类型**: {error_type}
- **错误信息**:
  ```
  {error}
  ```

"""
        
        if not failed_cases:
            failed_cases = "🎉 **所有测试都通过了！**\n"
        
        # 性能指标
        metrics_md = ""
        if metrics:
            avg_latency = metrics.get('avg_api_latency', 0)
            total_tokens = metrics.get('total_tokens', 0)
            avg_tokens = metrics.get('avg_tokens_per_task', 0)
            
            metrics_md = f"""
## 📊 性能指标

| 指标 | 值 |
|------|-----|
| 平均API延迟 | {avg_latency:.2f}秒 |
| 总Token使用量 | {total_tokens:,} |
| 平均Token/任务 | {avg_tokens:.0f} |

"""
        
        # 完整Markdown
        md = f"""# 🎯 评测报告

**生成时间**: {self.timestamp}

---

## 📈 总体统计

| 指标 | 数值 |
|------|------|
| 总任务数 | {total} |
| ✅ 通过 | {passed} |
| ❌ 失败 | {failed} |
| 📊 通过率 | **{pass_rate:.1%}** |

### 通过率进度条

```
{'█' * int(pass_rate * 50)}{'░' * (50 - int(pass_rate * 50))} {pass_rate:.1%}
```

---

## 📋 任务类型统计

{task_table}

---

{metrics_md}

---

## ❌ 失败案例详情

{failed_cases}

---

## 📝 备注

- 本报告由 Docker Build Evaluation System v2.0 自动生成
- 详细日志请查看 `logs/` 目录
- 完整结果请查看 `outputs/` 目录

---

*© 2024 - Powered by AI*
"""
        return md
    
    def _get_rate_color(self, rate: float) -> str:
        """根据通过率获取颜色"""
        if rate >= 0.9:
            return "#28a745"  # 绿色
        elif rate >= 0.7:
            return "#ffc107"  # 黄色
        elif rate >= 0.5:
            return "#fd7e14"  # 橙色
        else:
            return "#dc3545"  # 红色


def generate_reports(stats: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """
    生成所有格式的报告
    
    Args:
        stats: 统计数据
        output_dir: 输出目录
        
    Returns:
        生成的报告文件路径字典
    """
    generator = ReportGenerator()
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    reports = {}
    
    # 生成HTML报告
    html_file = output_dir / "report.html"
    reports['html'] = generator.generate_html_report(stats, html_file)
    
    # 生成Markdown报告
    md_file = output_dir / "report.md"
    reports['markdown'] = generator.generate_markdown_report(stats, md_file)
    
    logger.info(f"所有报告已生成在: {output_dir}")
    return reports


if __name__ == "__main__":
    # 测试
    test_stats = {
        'total': 10,
        'passed': 8,
        'failed': 2,
        'pass_rate': 0.8,
        'results': [
            {'tag': 'fix_bug', 'number': 1, 'pass': True},
            {'tag': 'fix_bug', 'number': 2, 'pass': False, 'error': 'Test failed', 'error_type': 'TestError', 'fail_step': 'validate'},
            {'tag': 'convert', 'number': 1, 'pass': True},
        ],
        'metrics': {
            'avg_api_latency': 2.5,
            'total_tokens': 15000,
            'avg_tokens_per_task': 1500
        }
    }
    
    reports = generate_reports(test_stats, Path('test_reports'))
    print(f"测试报告已生成:")
    for fmt, path in reports.items():
        print(f"  {fmt}: {path}")
