#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import argparse
import logging
from pathlib import Path

# 添加lib目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.config_manager import get_config
from lib.core.logger import LoggerManager, get_logger
from lib.core.evaluation_engine import EvaluationEngine
from lib.core.simple_data_manager import SimpleDataManager


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="代码评测系统 v2.0 - 完整版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置运行所有任务
  python bin/run_evaluation.py

  # 指定模型
  python bin/run_evaluation.py --model qwen3-235b-a22b-thinking-2507-fp8
  
  # 只运行特定任务类型
  python bin/run_evaluation.py --task-type fix_bug
  
  # 禁用流式API
  python bin/run_evaluation.py --no-stream
  
  # 指定输出目录
  python bin/run_evaluation.py --output ./my_results
        """
    )
    
    # 基本参数
    parser.add_argument(
        "--model",
        help="模型名称（覆盖配置文件）"
    )
    
    parser.add_argument(
        "--output",
        help="输出目录（覆盖配置文件）"
    )
    
    parser.add_argument(
        "--task-type",
        choices=["fix_bug", "convert", "refactor", "env", "sum", "split", "all"],
        default="all",
        help="任务类型（默认: all）"
    )
    
    # API参数
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="禁用流式API"
    )
    
    parser.add_argument(
        "--api-url",
        help="API地址（覆盖配置文件）"
    )
    
    parser.add_argument(
        "--api-key",
        help="API密钥（覆盖配置文件）"
    )
    
    # 配置文件
    parser.add_argument(
        "--config",
        help="配置文件路径"
    )
    
    # 其他选项
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别（默认: INFO）"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行（不实际调用API）"
    )
    
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="禁用自动备份数据集"
    )
    
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="禁用自动恢复数据集（保留修改）"
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    logger = get_logger(__name__)
    
    logger.info("="*70)
    logger.info("代码评测系统 v2.0")
    logger.info("="*70)
    
    # 加载配置
    try:
        config = get_config()
        if args.config:
            config.load_config(args.config)
        
        # 初始化日志系统
        log_level = getattr(logging, args.log_level)
        if args.verbose:
            log_level = logging.DEBUG
        
        # 从环境变量读取日志级别
        env_log_level = os.getenv('LOG_LEVEL', '').upper()
        if env_log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            log_level = getattr(logging, env_log_level)
        
        LoggerManager.initialize(config.paths.logs_dir, log_level)
        logger = get_logger(__name__)
        
        logger.info("=" * 70)
        logger.info("代码评测系统 v2.0 启动")
        logger.info("=" * 70)
        
        # 显示配置
        if args.verbose:
            config.print_config()
        else:
            logger.info(f"配置已加载")
            logger.info(f"  项目根目录: {config.project_root}")
            logger.info(f"  API地址: {config.api.base_url}")
            logger.info(f"  默认模型: {config.api.default_model}")
            logger.info(f"  流式模式: {'启用' if config.api.stream_enabled and not args.no_stream else '禁用'}")
            logger.info(f"  日志目录: {config.paths.logs_dir}")
            logger.info(f"  日志级别: {logging.getLevelName(log_level)}")
        
        logger.info(f"配置加载成功: project_root={config.project_root}")
        logger.info(f"日志级别: {logging.getLevelName(log_level)}")
        
        # 确保目录存在
        config.ensure_directories()
        logger.info("所有目录已确认")
        
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1
    
    # 准备运行
    logger.info("="*70)
    logger.info("准备评测")
    logger.info("="*70)
    
    model = args.model or config.api.default_model
    use_stream = config.api.stream_enabled and not args.no_stream
    output_dir = Path(args.output) if args.output else None
    
    logger.info(f"任务类型: {args.task_type}")
    logger.info(f"模型: {model}")
    logger.info(f"流式模式: {'是' if use_stream else '否'}")
    
    logger.info(f"评测参数: task_type={args.task_type}, model={model}, stream={use_stream}")
    
    if args.dry_run:
        logger.info("模拟运行模式（不会实际调用API）")
        logger.info("配置检查完成！")
        logger.info("模拟运行模式，退出")
        LoggerManager.shutdown()
        return 0
    
    # 运行评测
    try:
        logger.info("开始评测")
        
        # 创建数据集管理器
        auto_backup = not args.no_backup
        auto_restore = not args.no_restore
        
        if auto_backup:
            logger.info("📦 数据集管理:")
            logger.info(f"  自动备份: {'是' if auto_backup else '否'}")
            logger.info(f"  自动恢复: {'是' if auto_restore else '否'}")
        
        # 创建数据管理器
        data_manager = SimpleDataManager()
        
        # 如果启用了备份和恢复，使用上下文管理器
        if auto_backup and auto_restore:
            with data_manager.auto_restore_tasks():
                # 创建评测引擎
                engine = EvaluationEngine(model=model, use_stream=use_stream)
                
                # 运行评测
                stats = engine.run_evaluation(
                    task_type=args.task_type,
                    output_dir=output_dir
                )
        else:
            # 如果只备份不恢复，手动备份
            if auto_backup:
                logger.info("创建备份...")
                backup_success = data_manager.create_backup()
                if backup_success:
                    logger.info("数据集已备份")
                else:
                    logger.warning("备份失败，继续评测")
            
            # 创建评测引擎
            engine = EvaluationEngine(model=model, use_stream=use_stream)
            
            # 运行评测
            stats = engine.run_evaluation(
                task_type=args.task_type,
                output_dir=output_dir
            )
        
        logger.info("="*70)
        logger.info("评测完成！")
        logger.info("="*70)
        
        # 显示简洁的统计结果
        logger.info(f"📊 总体结果:")
        logger.info(f"  总任务数: {stats['total']}")
        logger.info(f"  通过: {stats['passed']} ✓")
        logger.info(f"  失败: {stats['failed']} ✗")
        logger.info(f"  通过率: {stats['pass_rate']:.1%}")
        
        logger.info(f"📈 执行统计:")
        logger.info(f"  平均轮数: {stats['round_stats']['avg_rounds']:.1f}")
        logger.info(f"  工具调用: {stats['tool_stats']['total_calls']} 次")
        
        logger.info(f"🔍 各任务类型:")
        for task_type, task_stats in stats['by_task_type'].items():
            status = "✓" if task_stats['pass_rate'] == 1.0 else "✗"
            logger.info(f"  {status} {task_type}: {task_stats['passed']}/{task_stats['total']} 通过")
        
        logger.info("=" * 70)
        logger.info("评测完成")
        logger.info(f"总任务数: {stats['total']}, 通过: {stats['passed']}, 失败: {stats['failed']}, 通过率: {stats['pass_rate']:.1%}")
        logger.info("=" * 70)
        
        LoggerManager.shutdown()
        return 0
        
    except KeyboardInterrupt:
        logger.warning("评测被用户中断")
        LoggerManager.shutdown()
        return 130
    
    except Exception as e:
        logger.error(f"评测失败: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        LoggerManager.shutdown()
        return 1


if __name__ == "__main__":
    sys.exit(main())
