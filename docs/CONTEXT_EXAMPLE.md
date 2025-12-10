# 三阶段评测上下文构建示例

## 测试用例：Bug修复任务 - 矩阵金币收集

### 初始信息

```json
{
  "test_case_id": "test_001",
  "user_question": "这个矩阵金币收集的代码有bug，找出并修复所有问题",
  "task_data": {
    "task_type": "fix_bug",
    "task_file": "data/tasks/bug_code/bug_code_1.py",
    "test_cases_file": "data/tasks/bug_test/case_1.json"
  }
}
```

---

## 阶段1：任务分解

### 输入上下文

```python
messages = [
    {
        "role": "system",
        "content": "你是一位资深且多面手的软件工程专家...\n\n##任务分解 目标描述：\n在回答问题前，识别用户的终极目标（goal）。将该目标原子化拆分为3-5个独立的子任务（task）...\n\n输出格式要求：\n# 目标\n{goal}\n\n# 任务要素\n- task1\n- task2\n- task3"
    },
    {
        "role": "user",
        "content": "这个矩阵金币收集的代码有bug，找出并修复所有问题"
    }
]
```

### 模型输出（用于评测）

```
# 目标
修复矩阵金币收集代码中的所有bug

# 任务要素
- 分析代码逻辑，识别金币收集算法的潜在错误
- 检查边界条件处理和数组越界问题
- 验证动态规划状态转移是否正确
- 测试修复后的代码，确保功能正常
```

**提取的任务列表（模型输出）**:
```python
model_tasks = [
    "分析代码逻辑，识别金币收集算法的潜在错误",
    "检查边界条件处理和数组越界问题",
    "验证动态规划状态转移是否正确",
    "测试修复后的代码，确保功能正常"
]
```

### 评测

```python
ground_truth_tasks = [
    "分析代码逻辑和问题描述",
    "检查边界条件处理",
    "验证动态规划状态转移",
    "检查障碍物处理逻辑",
    "修复identified的bugs",
    "编写测试用例",
    "测试修复后的代码"
]

# 使用LLM语义相似度判断
evaluation_result = {
    "recall": 0.57,      # 匹配到4个，共7个标准答案
    "precision": 1.0,    # 4个模型输出都匹配
    "f1_score": 0.73,
    "passed": True       # F1 >= 0.6
}
```

### 传递给下一阶段（关键！）

**注意：传递的是ground_truth，不是模型输出！**

```python
context_for_stage2 = {
    "tasks": ground_truth_tasks,  # ← 使用标准答案！
    "source": "ground_truth"
}
```

---

## 阶段2：任务规划

### 输入上下文

**关键：使用阶段1的ground_truth作为输入！**

```python
messages = [
    {
        "role": "system",
        "content": "你是一位资深且多面手的软件工程专家...\n\n##任务规划 \n目标描述：你将获得一个已经拆解好的子任务列表。请根据各子任务之间的依赖关系、可并行性和优先级，对它们进行分层排序...\n\n输出格式：[[子任务1, 子任务3], [子任务2], [子任务4, 子任务5]]"
    },
    {
        "role": "user",
        "content": "已拆解好的子任务列表：\n- 分析代码逻辑和问题描述\n- 检查边界条件处理\n- 验证动态规划状态转移\n- 检查障碍物处理逻辑\n- 修复identified的bugs\n- 编写测试用例\n- 测试修复后的代码"
    }
]
```

**说明**：用户消息中的任务列表来自 `ground_truth_tasks`，而不是模型在阶段1输出的任务！

### 模型输出（用于评测）

```
[
    ["分析代码逻辑和问题描述", "编写测试用例"],
    ["检查边界条件处理", "验证动态规划状态转移", "检查障碍物处理逻辑"],
    ["修复identified的bugs"],
    ["测试修复后的代码"]
]
```

**提取的规划（模型输出）**:
```python
model_plan = [
    ["分析代码逻辑和问题描述", "编写测试用例"],
    ["检查边界条件处理", "验证动态规划状态转移", "检查障碍物处理逻辑"],
    ["修复identified的bugs"],
    ["测试修复后的代码"]
]
```

### 评测

```python
# 依赖关系（ground_truth）
dependencies = {
    "检查边界条件处理": ["分析代码逻辑和问题描述"],
    "验证动态规划状态转移": ["分析代码逻辑和问题描述"],
    "检查障碍物处理逻辑": ["分析代码逻辑和问题描述"],
    "修复identified的bugs": ["检查边界条件处理", "验证动态规划状态转移", "检查障碍物处理逻辑"],
    "编写测试用例": ["分析代码逻辑和问题描述"],
    "测试修复后的代码": ["修复identified的bugs", "编写测试用例"]
}

evaluation_result = {
    "coverage": 1.0,              # 所有任务都在计划中
    "order_correctness": 0.9,     # 90%的依赖关系正确
    "level_efficiency": 0.85,     # 层级划分效率
    "overall_score": 0.92,
    "passed": True,
    "violations": [
        # "编写测试用例"应该在"测试修复后的代码"之前，但被放在了第一层
    ]
}
```

### 传递给下一阶段（关键！）

**注意：传递的是ground_truth plan，不是模型输出！**

```python
ground_truth_plan = [
    ["分析代码逻辑和问题描述"],
    ["检查边界条件处理", "验证动态规划状态转移", "检查障碍物处理逻辑", "编写测试用例"],
    ["修复identified的bugs"],
    ["测试修复后的代码"]
]

context_for_stage3 = {
    "plan": ground_truth_plan,  # ← 使用标准答案！
    "task_data": {
        "task_type": "fix_bug",
        "task_file": "data/tasks/bug_code/bug_code_1.py",
        "test_cases_file": "data/tasks/bug_test/case_1.json"
    },
    "source": "ground_truth"
}
```

---

## 阶段3：任务执行

### 输入上下文

**关键：使用阶段2的ground_truth plan作为执行计划！**

```python
messages = [
    {
        "role": "system",
        "content": "你是一位资深且多面手的软件工程专家...\n\n##任务执行 \n目标描述：你获得一个已排序的子任务列表，通过多轮执行这些子任务，每一轮对话只能解决一个子任务...\n\n工作流程：\n系统会给出一个已排好序的二维列表：\n[['分析代码逻辑和问题描述'], ['检查边界条件处理', '验证动态规划状态转移', '检查障碍物处理逻辑', '编写测试用例'], ['修复identified的bugs'], ['测试修复后的代码']]\n\n每个子任务按顺序独立完成..."
    },
    {
        "role": "user",
        "content": "请执行以下任务计划：\n[['分析代码逻辑和问题描述'], ['检查边界条件处理', '验证动态规划状态转移', '检查障碍物处理逻辑', '编写测试用例'], ['修复identified的bugs'], ['测试修复后的代码']]\n\n任务文件位于: data/tasks/bug_code/bug_code_1.py"
    }
]
```

**说明**：
1. 系统提示词中包含了 ground_truth_plan
2. 用户消息中也明确了执行计划
3. 提供了实际的任务文件路径

### 模型执行过程

**Round 1**: 执行"分析代码逻辑和问题描述"
```python
# 模型调用工具
tool_call: read_file("data/tasks/bug_code/bug_code_1.py")
# 模型输出分析结果
output: "代码中存在以下问题：1. 边界条件未处理..."
```

**Round 2**: 执行"检查边界条件处理"
```python
tool_call: search_files("边界条件")
output: "发现边界条件检查缺失在第15行..."
```

**Round 3**: 执行"验证动态规划状态转移"
```python
tool_call: read_file("data/tasks/bug_code/bug_code_1.py", line_start=20, line_end=40)
output: "状态转移方程有误..."
```

... （省略其他轮次）

**Round N**: 执行"测试修复后的代码"
```python
tool_call: execute_command("python data/tasks/bug_code/bug_code_1.py")
output: "所有测试通过"
```

### 评测

```python
# 运行测试用例
test_result = run_tests(
    code_file="data/tasks/bug_code/bug_code_1.py",
    test_cases_file="data/tasks/bug_test/case_1.json"
)

evaluation_result = {
    "total_rounds": 12,
    "tool_calls": 25,
    "passed": True,          # 所有测试用例通过
    "test_results": {
        "total": 5,
        "passed": 5,
        "failed": 0
    }
}
```

---

## 完整的上下文链

### 数据流向

```
初始问题
    ↓
[阶段1] 任务分解
    模型输出 → 评测（与ground_truth对比）
    ground_truth → 传递
    ↓
[阶段2] 任务规划
    输入：ground_truth tasks
    模型输出 → 评测（检查依赖和顺序）
    ground_truth plan → 传递
    ↓
[阶段3] 任务执行
    输入：ground_truth plan + task_data
    模型输出 → 评测（验证最终结果）
```

### 为什么这样设计？

#### 1. 保证评测的一致性

**如果使用模型输出传递**：
```
阶段1: 模型输出4个任务（少了3个）
    ↓
阶段2: 基于4个任务规划（信息不完整）
    ↓
阶段3: 基于不完整的计划执行（必然失败）
```

结果：无法评估阶段2和阶段3的真实能力

**使用ground_truth传递**：
```
阶段1: 模型输出4个任务 → 评测得分60%
    ↓ (传递ground_truth的7个任务)
阶段2: 基于完整的7个任务规划 → 评测得分90%
    ↓ (传递ground_truth的规划)
阶段3: 基于正确的计划执行 → 评测得分85%
```

结果：每个阶段都能独立评估，不受前序阶段影响

#### 2. 模拟真实场景的上下文连续性

虽然传递的是ground_truth，但：
- 系统提示词包含了任务的上下文
- 每个阶段都基于"正确的"上游输出
- 模拟了一个"理想情况"下的工作流程

#### 3. 可以评估每个阶段的独立能力

- 分解能力：能否正确理解问题并分解
- 规划能力：给定正确的任务，能否合理规划
- 执行能力：给定正确的计划，能否成功执行

---

## 最终结果结构

```json
{
  "test_case_id": "test_001",
  "test_case_name": "Bug修复任务 - 矩阵金币收集",
  
  "stages": {
    "decomposition": {
      "model_output": "# 目标\n修复矩阵金币收集代码中的所有bug\n\n# 任务要素\n...",
      "extracted_tasks": ["任务1", "任务2", "任务3", "任务4"],
      "ground_truth": ["任务1", "任务2", ..., "任务7"],
      "evaluation": {
        "recall": 0.57,
        "precision": 1.0,
        "f1_score": 0.73,
        "passed": true
      },
      "context_passed_to_next_stage": "ground_truth"
    },
    
    "planning": {
      "input_tasks": ["任务1", "任务2", ..., "任务7"],  // 来自ground_truth
      "model_output": "[['任务1', '任务6'], ['任务2', '任务3', '任务4'], ...]",
      "extracted_plan": [["任务1", "任务6"], ["任务2", "任务3", "任务4"], ...],
      "ground_truth_plan": [["任务1"], ["任务2", "任务3", "任务4", "任务6"], ...],
      "evaluation": {
        "coverage": 1.0,
        "order_correctness": 0.9,
        "overall_score": 0.92,
        "passed": true
      },
      "context_passed_to_next_stage": "ground_truth"
    },
    
    "execution": {
      "input_plan": [["任务1"], ["任务2", "任务3", "任务4", "任务6"], ...],  // 来自ground_truth
      "task_data": {...},
      "execution_log": [...],
      "evaluation": {
        "passed": true,
        "total_rounds": 12,
        "test_results": {"total": 5, "passed": 5}
      }
    }
  },
  
  "overall": {
    "all_stages_passed": true,
    "stage_scores": {
      "decomposition": 0.73,
      "planning": 0.92,
      "execution": 1.0
    },
    "average_score": 0.88
  }
}
```

---

## 关键点总结

1. ✅ **评测模型输出**：每个阶段都评测模型的实际表现
2. ✅ **传递ground_truth**：保证下游阶段基于正确的上下文
3. ✅ **上下文连续性**：通过ground_truth维护稳定的上下文链
4. ✅ **独立评估**：每个阶段的评测不受前序阶段影响
5. ✅ **完整记录**：保存模型输出、ground_truth、评测结果
