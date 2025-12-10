# 三阶段评测系统设计

## 核心理念

三阶段评测是对**同一个任务**连续执行三个阶段，每个阶段的输入依赖于上一个阶段的输出。

## 正确的流程

```
用户问题
    ↓
【阶段1：任务分解】
    输入：用户问题
    输出：子任务列表
    ↓
【阶段2：任务规划】
    输入：阶段1输出的子任务列表
    输出：带依赖关系的任务计划
    ↓
【阶段3：任务执行】
    输入：阶段2输出的任务计划 + 原始任务数据
    输出：执行结果
    ↓
最终验证
```

## 错误的流程（当前实现）

```
任务A → 任务分解 → 验证
任务B → 任务分解 → 验证
任务C → 任务分解 → 验证

任务D → 任务规划 → 验证  ❌ 使用预设的任务列表
任务E → 任务规划 → 验证
任务F → 任务规划 → 验证

任务G → 任务执行 → 验证
```

## 正确的数据结构

### 测试用例格式

```json
{
  "id": "test_case_001",
  "name": "Bug修复任务 - 矩阵金币收集",
  "description": "完整的三阶段评测",
  
  "initial_question": "这个矩阵金币收集的代码有bug，找出并修复所有问题",
  
  "task_data": {
    "task_type": "fix_bug",
    "task_dir": "data/tasks/bug_code/bug_code_1",
    "test_cases_file": "data/tasks/bug_test/case_1.json"
  },
  
  "stages": {
    "decomposition": {
      "ground_truth": [
        "分析代码逻辑和问题描述",
        "检查边界条件处理",
        "验证动态规划状态转移",
        "修复identified的bugs",
        "测试修复后的代码"
      ],
      "evaluation": {
        "min_recall": 0.6,
        "min_precision": 0.6
      }
    },
    
    "planning": {
      "dependencies": {
        "检查边界条件处理": ["分析代码逻辑和问题描述"],
        "验证动态规划状态转移": ["分析代码逻辑和问题描述"],
        "修复identified的bugs": ["检查边界条件处理", "验证动态规划状态转移"],
        "测试修复后的代码": ["修复identified的bugs"]
      },
      "evaluation": {
        "min_coverage": 0.8,
        "min_order_correctness": 0.8
      }
    },
    
    "execution": {
      "max_rounds": 15,
      "evaluation": {
        "must_pass": true
      }
    }
  }
}
```

## 执行流程

### 1. 初始化

```python
test_case = load_test_case("test_case_001.json")
result = {
    "test_case_id": test_case["id"],
    "stages": {}
}
```

### 2. 阶段1：任务分解

```python
# 输入：用户问题
user_question = test_case["initial_question"]

# 调用模型
decomposition_response = model.chat_completion(
    system_prompt=get_decomposition_prompt(),
    user_message=user_question
)

# 提取任务
extracted_tasks = extract_tasks_from_response(decomposition_response)

# 验证
decomp_result = validate_task_decomposition(
    model_tasks=extracted_tasks,
    ground_truth=test_case["stages"]["decomposition"]["ground_truth"]
)

result["stages"]["decomposition"] = {
    "model_output": decomposition_response,
    "extracted_tasks": extracted_tasks,
    "validation": decomp_result,
    "pass": decomp_result["recall"] >= 0.6 and decomp_result["precision"] >= 0.6
}
```

### 3. 阶段2：任务规划

```python
# 输入：阶段1输出的任务列表
tasks_for_planning = extracted_tasks  # 使用实际提取的任务！

# 构建用户消息
user_message = "已拆解好的子任务列表：\n" + "\n".join([f"- {task}" for task in tasks_for_planning])

# 调用模型
planning_response = model.chat_completion(
    system_prompt=get_planning_prompt(),
    user_message=user_message
)

# 提取计划
planned_order = extract_plan_from_response(planning_response)

# 验证（使用ground_truth中的依赖关系）
planning_result = validate_task_planning(
    model_plan=planned_order,
    ground_truth_tasks=tasks_for_planning,  # 注意：使用实际的任务列表
    dependencies=test_case["stages"]["planning"]["dependencies"]
)

result["stages"]["planning"] = {
    "model_output": planning_response,
    "extracted_plan": planned_order,
    "validation": planning_result,
    "pass": planning_result["coverage"] >= 0.8
}
```

### 4. 阶段3：任务执行

```python
# 输入：阶段2输出的任务计划 + 原始任务数据
task_plan = planned_order
task_data = test_case["task_data"]

# 执行任务
execution_result = execute_task_with_plan(
    task_type=task_data["task_type"],
    task_dir=task_data["task_dir"],
    task_plan=task_plan,  # 使用实际规划的顺序
    max_rounds=test_case["stages"]["execution"]["max_rounds"]
)

result["stages"]["execution"] = {
    "execution_log": execution_result,
    "validation": validate_execution_result(execution_result, task_data),
    "pass": execution_result["passed"]
}
```

### 5. 整体评价

```python
result["overall"] = {
    "all_stages_passed": all([
        result["stages"]["decomposition"]["pass"],
        result["stages"]["planning"]["pass"],
        result["stages"]["execution"]["pass"]
    ]),
    "final_score": calculate_overall_score(result)
}
```

## 关键改进点

### 1. 数据流连续性

```python
# ❌ 错误：每个阶段独立
decomposition_test_cases = load("decomposition.json")
planning_test_cases = load("planning.json")  # 使用预设任务列表

# ✅ 正确：阶段间传递数据
test_case = load("full_test_case.json")
tasks = run_decomposition(test_case.question)
plan = run_planning(tasks)  # 使用上一阶段的输出
result = run_execution(plan, test_case.task_data)
```

### 2. 验证标准调整

- **分解阶段**: 验证提取的任务与ground_truth的相似度
- **规划阶段**: 验证规划是否覆盖了分解阶段输出的任务（而不是ground_truth任务）
- **执行阶段**: 验证按照规划的顺序执行是否成功

### 3. 容错机制

如果某个阶段失败，可以：
- **方案A**: 使用ground_truth继续下一阶段（测试模型恢复能力）
- **方案B**: 终止评测，记录失败阶段（严格模式）

## 实现建议

### 新的评测入口

```python
def run_three_stage_evaluation(test_case_file: str, fallback_mode: str = "ground_truth"):
    """
    运行完整的三阶段评测
    
    Args:
        test_case_file: 测试用例文件
        fallback_mode: 阶段失败时的处理方式
            - "ground_truth": 使用标准答案继续
            - "stop": 终止评测
    """
    test_case = load_test_case(test_case_file)
    result = {}
    
    # 阶段1：任务分解
    decomp_result, extracted_tasks = run_decomposition_stage(test_case)
    result["decomposition"] = decomp_result
    
    # 决定规划阶段的输入
    if decomp_result["pass"] or fallback_mode == "ground_truth":
        tasks_for_planning = extracted_tasks if decomp_result["pass"] else test_case["stages"]["decomposition"]["ground_truth"]
    else:
        return result  # 终止评测
    
    # 阶段2：任务规划
    planning_result, task_plan = run_planning_stage(test_case, tasks_for_planning)
    result["planning"] = planning_result
    
    # 决定执行阶段的输入
    if planning_result["pass"] or fallback_mode == "ground_truth":
        plan_for_execution = task_plan if planning_result["pass"] else create_default_plan(tasks_for_planning)
    else:
        return result
    
    # 阶段3：任务执行
    execution_result = run_execution_stage(test_case, plan_for_execution)
    result["execution"] = execution_result
    
    return result
```

## 下一步工作

1. 重新设计测试用例数据结构
2. 修改 `bin/run_stage_evaluation.py` 实现连续流程
3. 更新验证器支持动态任务列表
4. 添加阶段间数据传递机制
5. 实现容错和fallback逻辑
