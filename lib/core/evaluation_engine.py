#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评测引擎
核心评测逻辑
"""

import sys
import json
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.core.config_manager import get_config
from lib.core.logger import get_logger
from lib.api.client import APIClient, APIError
from lib.api.judge_client import get_judge_client
from lib.tools.tool_executor import run_tool_calls
from lib.core.utils import read_json, append_to_json_file

# 导入验证器
from lib.validators.bugcode import validate
from lib.validators.convert import validate_js_cases
from lib.validators.refactor import validate_refactor
from lib.validators.env import validate_env
from lib.validators.summary import validate_sum
from lib.validators.split import validate_split
from lib.core.simple_data_manager import get_simple_data_manager

# 创建logger
logger = get_logger(__name__)


class EvaluationEngine:
    """评测引擎"""
    
    def __init__(self, model: Optional[str] = None, use_stream: bool = True):
        """
        初始化评测引擎
        
        Args:
            model: 模型名称（被测试的模型）
            use_stream: 是否使用流式API
        """
        self.config = get_config()
        self.model = model or self.config.api.default_model
        self.use_stream = use_stream and self.config.api.stream_enabled
        self.client = APIClient(model=self.model)
        
        # 初始化Judge客户端（用于评估sum/split任务）
        self.judge_client = get_judge_client()
        
        logger.info(f"评测引擎已初始化: model={self.model}, stream={self.use_stream}")
        if self.judge_client.available:
            judge_model = self.config.get('evaluation', {}).get('judge_model', {}).get('model', 'Unknown')
            logger.info(f"Judge客户端可用: model={judge_model}")
        else:
            logger.info("Judge客户端不可用，sum/split任务将使用规则评估")
        
        logger.info(f"评测引擎已初始化: model={self.model}, stream={self.use_stream}")
        
    def run_single_task(self, 
                       question: Dict[str, Any],
                       ground_truth: Dict[str, Any],
                       system_prompt: str,
                       tools: List[Dict],
                       output_file: Path) -> Dict[str, Any]:
        """
        运行单个评测任务
        
        Args:
            question: 问题数据
            ground_truth: 标准答案
            system_prompt: 系统提示词
            tools: 工具定义
            output_file: 输出文件
            
        Returns:
            评测结果
        """
        answer = dict(question)
        answer["use_tools"] = []
        answer["metrics"] = {
            "total_rounds": 0,
            "tool_calls": 0,
            "tool_types": {},  # 每种工具的调用次数
            "output_chars": 0
        }
        current_step = "start"
        tmp_files: List[Path] = []
        
        try:
            # 构造初始消息
            current_step = "prepare_messages"
            logger.debug(f"开始执行任务: tag={question.get('tag')}, number={question.get('number')}")
            
            base_path = str(self.config.tasks.data_dirs.get(question['tag'], Path.cwd()))
            logger.debug(f"工作目录: {base_path}")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "##任务分解:\n" + ground_truth['question']},
                {"role": "assistant", "content": question['answer']},
                {"role": "user", "content": "我了解你的答案了，结合你的答案和我个人的理解，我得到了一个分解后的任务列表，现在进行任务规划：\n" + str(ground_truth["SubTasks"])},
                {"role": "assistant", "content": str(question["plan_answer"])},
                {"role": "user", "content": "当前工作目录：" + base_path + " \n\n ##任务执行:\n" + str(ground_truth["plan_answer"]) + question.get("sums", "")},
            ]
            
            # 多轮对话
            round_idx = 0
            max_rounds = self.config.tasks.max_rounds
            logger.info(f"开始多轮对话，最大轮数: {max_rounds}")
            
            while round_idx < max_rounds:
                round_idx += 1
                logger.info(f"===== {self.model} Round {round_idx}/{max_rounds} =====")
                current_step = f"api_round_{round_idx}"
                
                try:
                    # 调用API
                    if self.use_stream:
                        logger.info("正在以流式模式调用API...")
                        try:
                            stream = self.client.chat_completion_stream(
                                messages=messages,
                                tools=tools
                            )
                            resp = self.client.reconstruct_from_stream(stream)
                            logger.debug("流式API调用成功")
                        except (APIError, Exception) as stream_error:
                            logger.error(f"流式API失败: {stream_error}")
                            if self.config.api.stream_fallback:
                                logger.info("尝试fallback到非流式API")
                                resp = self.client.chat_completion(
                                    messages=messages,
                                    tools=tools
                                )
                                logger.info("非流式API fallback成功")
                            else:
                                raise
                    else:
                        logger.info("正在以非流式模式调用API...")
                        resp = self.client.chat_completion(
                            messages=messages,
                            tools=tools
                        )
                    
                    # 验证响应
                    if not resp or 'choices' not in resp:
                        error_msg = f"API返回了无效的响应: {resp}"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    
                    # 保存响应
                    answer[f"round{round_idx}"] = resp['choices'][0]['message']
                    messages.append(answer[f"round{round_idx}"])
                    
                    # 检查是否有工具调用
                    if not answer[f'round{round_idx}'].get('tool_calls'):
                        logger.warning("未检测到工具调用，任务结束")
                        break
                    
                    # 执行工具
                    current_step = f"run_tool_round_{round_idx}"
                    tool_calls = list(answer[f'round{round_idx}']['tool_calls'])
                    tool_name = tool_calls[0]['function']['name']
                    logger.info(f"执行工具: {tool_name}")
                    
                    # 根据任务类型决定是否使用虚拟环境
                    use_venv = (question['tag'] == "env")
                    venv_path = None
                    if use_venv:
                        logger.debug("使用虚拟环境执行")
                        # 使用配置文件中的虚拟环境路径
                        venv_path = self.config.paths.venv_dir
                    
                    try:
                        model_run_out = run_tool_calls(tool_calls, base_path, use_venv, venv_path)
                        logger.debug(f"工具执行完成: {tool_name}")
                    except Exception as tool_error:
                        logger.error(f"工具执行失败: {tool_error}")
                        raise
                    
                    # 记录使用的工具
                    answer['use_tools'].append(tool_calls[0]['function']['name'])
                    
                    # 更新指标
                    tool_name_key = tool_calls[0]['function']['name']
                    answer['metrics']['tool_calls'] += 1
                    if tool_name_key not in answer['metrics']['tool_types']:
                        answer['metrics']['tool_types'][tool_name_key] = 0
                    answer['metrics']['tool_types'][tool_name_key] += 1
                    
                    # 添加工具结果到消息
                    # 检查工具执行是否出错
                    if "error" in model_run_out:
                        # 工具执行失败
                        tool_result_content = f"工具执行失败: {model_run_out['error']}"
                        logger.warning(f"工具执行失败: {model_run_out['error']}")
                    else:
                        # 工具执行成功
                        tool_result_content = model_run_out.get("result", "")
                    
                    answer[f"round{round_idx}_tool_call"] = {
                        "role": "tool",
                        "tool_call_id": model_run_out.get("id", ""),
                        "content": tool_result_content
                    }
                    messages.append({
                        "role": "tool",
                        "tool_call_id": model_run_out.get("id", ""),
                        "content": tool_result_content
                    })
                    
                except APIError as api_error:
                    logger.error(f"API错误 (Round {round_idx}): {api_error}")
                    answer[f'round{round_idx}_error'] = {
                        'type': 'APIError',
                        'message': str(api_error),
                        'status_code': getattr(api_error, 'status_code', None)
                    }
                    break
                except Exception as api_error:
                    logger.error(f"Round {round_idx} 失败: {api_error}\n{traceback.format_exc()}")
                    answer[f'round{round_idx}_error'] = {
                        'type': type(api_error).__name__,
                        'message': str(api_error)
                    }
                    break
            
            # 验证结果
            current_step = "validate_result"
            logger.info("开始验证结果")
            answer['pass'] = self._validate_result(question, tmp_files)
            result_text = "通过" if answer['pass'] else "失败"
            logger.info(f"验证结果: {result_text}")
            
            # 统计指标
            # 统计对话轮次
            round_count = 0
            for key in answer.keys():
                if key.startswith('round') and not key.endswith('_tool_call') and not key.endswith('_error'):
                    round_count += 1
            answer['metrics']['total_rounds'] = round_count
            
            # 统计输出字符数
            total_output = 0
            for key, value in answer.items():
                if key.startswith('round') and isinstance(value, dict):
                    content = value.get('content', '')
                    if content:
                        total_output += len(str(content))
            answer['metrics']['output_chars'] = total_output
            
            # 记录工具调用种类数
            answer['metrics']['unique_tools'] = len(answer['metrics']['tool_types'])
            
        except FileNotFoundError as exc:
            logger.error(f"文件未找到 '{current_step}': {exc}")
            answer['pass'] = False
            answer['fail_step'] = current_step
            answer['error'] = f"文件未找到: {str(exc)}"
            answer['error_type'] = 'FileNotFoundError'
            logger.error(f"文件未找到 '{current_step}': {exc}")
        except json.JSONDecodeError as exc:
            logger.error(f"JSON解析错误 '{current_step}': {exc}")
            answer['pass'] = False
            answer['fail_step'] = current_step
            answer['error'] = f"JSON解析错误: {str(exc)}"
            answer['error_type'] = 'JSONDecodeError'
            logger.error(f"JSON解析错误 '{current_step}': {exc}")
        except APIError as exc:
            logger.error(f"API错误 '{current_step}': {exc}")
            answer['pass'] = False
            answer['fail_step'] = current_step
            answer['error'] = str(exc)
            answer['error_type'] = 'APIError'
            answer['status_code'] = getattr(exc, 'status_code', None)
            logger.error(f"API错误 '{current_step}': {exc}")
        except Exception as exc:
            logger.error(f"未预期错误 '{current_step}': {exc}\n{traceback.format_exc()}")
            answer['pass'] = False
            answer['fail_step'] = current_step
            answer['error'] = str(exc)
            answer['error_type'] = type(exc).__name__
            answer['traceback'] = traceback.format_exc()
            logger.error(f"错误 '{current_step}': {exc}")
        
        finally:
            # 清理临时文件
            if tmp_files:
                logger.debug(f"清理 {len(tmp_files)} 个临时文件")
            self._cleanup_temp_files(tmp_files)
        
        # 保存结果
        answer['messages'] = messages
        append_to_json_file(answer, output_file)
        
        return answer
    
    def _validate_result(self, question: Dict[str, Any], tmp_files: List[Path]) -> bool:
        """验证结果"""
        num = question['number']
        tag = question['tag']
        
        logger.debug(f"验证任务: tag={tag}, number={num}")
        
        try:
            if tag == "fix_bug":
                fixed_file = self.config.tasks.data_dirs['fix_bug'] / f"fix_code_{num}.py"
                test_file = self.config.tasks.data_dirs['bug_test'].parent / "bug_test" / f"test_{num}.txt"
                tmp_files.append(fixed_file)
                logger.debug(f"验证bug修复: fixed={fixed_file}, test={test_file}")
                result = validate(fixed_file, test_file, list(question["test_case"]))
                return result
            
            elif tag == "convert":
                js_file = self.config.tasks.data_dirs['convert'] / f"js_{num}.js"
                cases_file = self.config.tasks.data_dirs['convert'] / f"case_{num}.json"
                tmp_files.append(js_file)
                logger.debug(f"验证代码转换: js={js_file}")
                result = validate_js_cases(js_file, cases_file)
                return result
            
            elif tag == "refactor":
                # Refactor任务：模型会直接修改文件
                refactor_file = self.config.tasks.data_dirs['refactor'] / f"utils_{num}.py"
                expected_output_file = self.config.tasks.data_dirs['refactor'] / f"expected_output_{num}.txt"
                
                logger.debug(f"验证代码重构: file={refactor_file}")
                logger.debug(f"  重命名映射: {question.get('names', {})}")
                
                # 调用新的验证器
                result = validate_refactor(
                    file_path=str(refactor_file),
                    rename_map=question.get("names", {}),
                    expected_output_file=str(expected_output_file) if expected_output_file.exists() else None,
                    run_script=True
                )
                return result
            
            elif tag == "env":
                env_file = self.config.tasks.data_dirs['env'] / f"env_{num}.py"
                logger.debug(f"验证环境配置: file={env_file}")
                result = validate_env(env_file, venv_dir=str(self.config.paths.venv_dir))
                return result
            
            elif tag == "sum":
                md_file = self.config.tasks.data_dirs['sum'] / f"sample_scraper_{num}" / "README.md"
                src_dir = self.config.tasks.data_dirs['sum'] / f"sample_scraper_{num}" / "src"
                tmp_files.append(md_file)
                logger.debug(f"验证总结: file={md_file}, src={src_dir}")
                
                # 调用validate_sum，使用JudgeClient而不是主API client
                passed, details = validate_sum(
                    md_file=md_file,
                    src_dir=src_dir if src_dir.exists() else None,
                    judge_client=self.judge_client,  # 使用Judge客户端
                    use_llm=True  # 优先使用LLM评估
                )
                logger.info(f"总结评估: 通过={passed}, 评分={details.get('score', 0):.2f}, 方法={details.get('method')}")
                return passed
            
            elif tag == "split":
                cases_file = self.config.tasks.data_dirs['split'] / f"case_{num}.py"
                fixed_file = self.config.tasks.data_dirs['split'] / f"fix_{num}.py"
                tmp_files.append(fixed_file)
                logger.debug(f"验证代码拆分: orig={cases_file}, split={fixed_file}")
                
                # 调用validate_split，使用JudgeClient而不是主API client
                passed, details = validate_split(
                    file_orig=str(cases_file),
                    file_split=str(fixed_file),
                    function_name=question.get("function", "giant_cleaner"),  # 默认函数名
                    judge_client=self.judge_client,  # 使用Judge客户端
                    use_llm=True,  # 优先使用LLM评估
                    mute=True
                )
                logger.info(f"拆分评估: 通过={passed}, 评分={details.get('score', 0):.2f}, 方法={details.get('method')}")
                return passed
            
            else:
                logger.warning(f"未知任务类型: {tag}")
                logger.warning(f"未知任务类型: {tag}")
                return False
                
        except Exception as e:
            logger.error(f"验证失败: {e}\n{traceback.format_exc()}")
            logger.error(f"验证失败: {e}")
            return False
    
    def _cleanup_temp_files(self, tmp_files: List[Path]):
        """清理临时文件"""
        for f in tmp_files:
            try:
                if f.exists():
                    f.unlink()
                    logger.debug(f"删除临时文件: {f.name}")
            except Exception as e:
                logger.warning(f"删除文件失败 {f}: {e}")
    
    def run_evaluation(self,
                      task_type: str = "all",
                      output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        运行完整评测
        
        Args:
            task_type: 任务类型
            output_dir: 输出目录
            
        Returns:
            评测统计结果
        """
        # 使用强制数据恢复
        data_manager = get_simple_data_manager()
        
        with data_manager.auto_restore_tasks():
            return self._run_evaluation_internal(task_type, output_dir)
    
    def _run_evaluation_internal(self,
                                 task_type: str = "all",
                                 output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        内部评测执行（在数据恢复保护下运行）
        
        Args:
            task_type: 任务类型
            output_dir: 输出目录
            
        Returns:
            评测统计结果
        """
        logger.info("="*70)
        logger.info("开始评测")
        logger.info("="*70)
        
        # 确定输出目录
        if output_dir is None:
            output_dir = self.config.paths.outputs_dir / f"eval_{int(time.time())}"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载测试数据
        test_file = self.config.paths.test_cases_dir / "exe_task_total.json"
        questions = read_json(test_file)
        
        # 筛选任务
        if task_type != "all":
            questions = [q for q in questions if q.get('tag') == task_type]
        
        logger.info(f"任务数量: {len(questions)}")
        logger.info(f"输出目录: {output_dir}")
        
        # 加载系统提示词和工具
        system_prompt_file = self.config.paths.prompts_dir / "system_prompt_2.json"
        tool_list_file = self.config.paths.prompts_dir / "tool_list.json"
        
        system_prompt_data = read_json(system_prompt_file)
        tools = read_json(tool_list_file)
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt(system_prompt_data, questions)
        
        # 运行评测
        results = []
        for idx, question in enumerate(questions, 1):
            logger.info(f"{'='*70}")
            logger.info(f"任务 {idx}/{len(questions)}: {question.get('tag')} - {question.get('number')}")
            logger.info(f"{'='*70}")
            
            output_file = output_dir / f"result_{idx}.json"
            
            try:
                result = self.run_single_task(
                    question=question,
                    ground_truth=question,  # 使用自身作为GT
                    system_prompt=system_prompt,
                    tools=tools,
                    output_file=output_file
                )
                results.append(result)
                
                status = "✅ 通过" if result.get('pass') else "❌ 失败"
                logger.info(f"结果: {status}")
                
                # 输出该任务的指标
                metrics = result.get('metrics', {})
                logger.info(f"指标: 轮次={metrics.get('total_rounds', 0)}, "
                          f"工具调用={metrics.get('tool_calls', 0)}, "
                          f"工具种类={metrics.get('unique_tools', 0)}, "
                          f"输出字符={metrics.get('output_chars', 0)}")
                if metrics.get('tool_types'):
                    tool_list = ', '.join([f"{t}×{c}" for t, c in metrics['tool_types'].items()])
                    logger.info(f"工具详情: {tool_list}")
                
            except Exception as e:
                logger.error(f"任务执行失败: {e}")
                logger.error(traceback.format_exc())
        
        # 统计结果
        stats = self._calculate_stats(results)
        
        # 保存统计
        stats_file = output_dir / "summary.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        # 打印详细统计
        logger.info("="*70)
        logger.info("📊 评测完成 - 详细统计")
        logger.info("="*70)
        
        # 基本统计
        logger.info(f"✅ 基本统计:")
        logger.info(f"  总任务数: {stats['total']}")
        logger.info(f"  通过: {stats['passed']} ({stats['pass_rate']:.1%})")
        logger.info(f"  失败: {stats['failed']}")
        
        # 工具调用统计
        tool_stats = stats['tool_stats']
        logger.info(f"🔧 工具调用统计:")
        logger.info(f"  总调用次数: {tool_stats['total_calls']}")
        logger.info(f"  平均每任务: {tool_stats['avg_calls_per_task']:.2f} 次")
        logger.info(f"  使用的工具种类: {len(tool_stats['tool_types'])} 种")
        if tool_stats['tool_types']:
            logger.info(f"  工具使用排行:")
            sorted_tools = sorted(tool_stats['tool_types'].items(), 
                                key=lambda x: x[1], reverse=True)
            for tool_name, count in sorted_tools[:5]:  # 显示前5个
                logger.info(f"    - {tool_name}: {count} 次")
        
        # 对话轮次统计
        round_stats = stats['round_stats']
        logger.info(f"💬 对话轮次统计:")
        logger.info(f"  总轮次: {round_stats['total_rounds']}")
        logger.info(f"  平均轮次: {round_stats['avg_rounds']:.2f}")
        logger.info(f"  最大轮次: {round_stats['max_rounds']}")
        logger.info(f"  最小轮次: {round_stats['min_rounds']}")
        
        # 输出统计
        output_stats = stats['output_stats']
        logger.info(f"📝 输出统计:")
        logger.info(f"  总字符数: {output_stats['total_chars']:,}")
        logger.info(f"  平均每任务: {output_stats['avg_chars_per_task']:.0f} 字符")
        logger.info(f"  最大输出: {output_stats['max_chars']:,} 字符")
        logger.info(f"  最小输出: {output_stats['min_chars']:,} 字符")
        
        # 按任务类型统计
        logger.info(f"📋 按任务类型统计:")
        for task_type, type_stats in stats['by_task_type'].items():
            logger.info(f"  {task_type}:")
            logger.info(f"    任务数: {type_stats['total']}")
            logger.info(f"    通过率: {type_stats['pass_rate']:.1%}")
            logger.info(f"    平均轮次: {type_stats['avg_rounds']:.2f}")
            logger.info(f"    工具调用: {type_stats['tool_calls']} 次")
            logger.info(f"    平均输出: {type_stats.get('avg_output_chars', 0):.0f} 字符")
        
        # 错误统计
        if stats['error_stats']['total_errors'] > 0:
            error_stats = stats['error_stats']
            logger.info(f"❌ 错误统计:")
            logger.info(f"  总错误数: {error_stats['total_errors']}")
            if error_stats['error_types']:
                logger.info(f"  错误类型分布:")
                for error_type, count in error_stats['error_types'].items():
                    logger.info(f"    - {error_type}: {count} 次")
            if error_stats['fail_steps']:
                logger.info(f"  失败步骤分布:")
                for step, count in sorted(error_stats['fail_steps'].items(), 
                                         key=lambda x: x[1], reverse=True)[:3]:
                    logger.info(f"    - {step}: {count} 次")
        
        logger.info(f"💾 结果保存到: {output_dir}")
        logger.info("="*70)
        
        return stats
    
    def _build_system_prompt(self, prompt_data: Dict, questions: List[Dict]) -> str:
        """构建系统提示词"""
        # 简化版本，直接使用base提示词
        return prompt_data.get('base', '')
    
    def _calculate_stats(self, results: List[Dict]) -> Dict[str, Any]:
        """
        计算详细的统计信息
        
        包括：
        - 基本指标：总数、通过数、失败数、通过率
        - 工具调用统计：总次数、成功率、各工具使用次数
        - 对话轮次统计：平均轮次、最大轮次
        - 输出统计：总字符数、平均字符数
        - 按任务类型分组统计
        """
        total = len(results)
        passed = sum(1 for r in results if r.get('pass', False))
        failed = total - passed
        
        # 工具调用统计
        tool_stats = {
            'total_calls': 0,
            'tool_types': {},  # 每种工具的使用次数
            'avg_calls_per_task': 0
        }
        
        # 对话轮次统计
        round_stats = {
            'total_rounds': 0,
            'avg_rounds': 0,
            'max_rounds': 0,
            'min_rounds': float('inf')
        }
        
        # 输出统计
        output_stats = {
            'total_chars': 0,
            'avg_chars_per_task': 0,
            'max_chars': 0,
            'min_chars': float('inf')
        }
        
        # 按任务类型统计
        by_task_type = {}
        
        # 错误统计
        error_stats = {
            'total_errors': 0,
            'error_types': {},
            'fail_steps': {}
        }
        
        for result in results:
            task_type = result.get('tag', 'unknown')
            
            # 初始化任务类型统计
            if task_type not in by_task_type:
                by_task_type[task_type] = {
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'pass_rate': 0,
                    'avg_rounds': 0,
                    'total_rounds': 0,
                    'tool_calls': 0,
                    'total_output_chars': 0
                }
            
            by_task_type[task_type]['total'] += 1
            if result.get('pass', False):
                by_task_type[task_type]['passed'] += 1
            else:
                by_task_type[task_type]['failed'] += 1
            
            # 使用已经计算好的 metrics
            metrics = result.get('metrics', {})
            
            # 统计工具调用（使用 metrics）
            tool_calls_count = metrics.get('tool_calls', 0)
            tool_stats['total_calls'] += tool_calls_count
            by_task_type[task_type]['tool_calls'] += tool_calls_count
            
            # 从 metrics 中获取工具类型统计
            for tool_name, count in metrics.get('tool_types', {}).items():
                if tool_name not in tool_stats['tool_types']:
                    tool_stats['tool_types'][tool_name] = 0
                tool_stats['tool_types'][tool_name] += count
            
            # 统计对话轮次（使用 metrics）
            round_count = metrics.get('total_rounds', 0)
            if round_count > 0:
                round_stats['total_rounds'] += round_count
                round_stats['max_rounds'] = max(round_stats['max_rounds'], round_count)
                round_stats['min_rounds'] = min(round_stats['min_rounds'], round_count)
                by_task_type[task_type]['total_rounds'] += round_count
            
            # 统计输出字符数（使用 metrics）
            output_chars = metrics.get('output_chars', 0)
            if output_chars > 0:
                output_stats['total_chars'] += output_chars
                output_stats['max_chars'] = max(output_stats['max_chars'], output_chars)
                output_stats['min_chars'] = min(output_stats['min_chars'], output_chars)
                by_task_type[task_type]['total_output_chars'] += output_chars
            
            # 统计错误
            if not result.get('pass', False):
                error_stats['total_errors'] += 1
                
                error_type = result.get('error_type', 'Unknown')
                if error_type not in error_stats['error_types']:
                    error_stats['error_types'][error_type] = 0
                error_stats['error_types'][error_type] += 1
                
                fail_step = result.get('fail_step', 'Unknown')
                if fail_step not in error_stats['fail_steps']:
                    error_stats['fail_steps'][fail_step] = 0
                error_stats['fail_steps'][fail_step] += 1
        
        # 计算平均值
        if total > 0:
            tool_stats['avg_calls_per_task'] = tool_stats['total_calls'] / total
            round_stats['avg_rounds'] = round_stats['total_rounds'] / total
            output_stats['avg_chars_per_task'] = output_stats['total_chars'] / total
        
        if round_stats['min_rounds'] == float('inf'):
            round_stats['min_rounds'] = 0
        if output_stats['min_chars'] == float('inf'):
            output_stats['min_chars'] = 0
        
        # 计算各任务类型的平均值和通过率
        for task_type in by_task_type:
            stats = by_task_type[task_type]
            if stats['total'] > 0:
                stats['pass_rate'] = stats['passed'] / stats['total']
                stats['avg_rounds'] = stats['total_rounds'] / stats['total']
                stats['avg_output_chars'] = stats['total_output_chars'] / stats['total']
        
        return {
            # 基本统计
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / total if total > 0 else 0,
            
            # 工具调用统计
            'tool_stats': tool_stats,
            
            # 对话轮次统计
            'round_stats': round_stats,
            
            # 输出统计
            'output_stats': output_stats,
            
            # 错误统计
            'error_stats': error_stats,
            
            # 按任务类型统计
            'by_task_type': by_task_type,
            
            # 原始结果
            'results': results
        }


if __name__ == "__main__":
    # 测试
    engine = EvaluationEngine()
    logger.info("评测引擎已创建")
