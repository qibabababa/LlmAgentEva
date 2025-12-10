# AI代码评测系统

一个完整的AI代码能力评测系统，支持传统单阶段评测和创新的三阶段连续评测。

## 特性

### 🔧 传统评测（单阶段）
- **6种任务类型**: Bug修复、代码转换、代码重构、环境配置、代码摘要、代码拆分
- **自动化验证**: AST分析、测试执行、LLM Judge评估
- **详细指标**: 工具调用统计、对话轮次、输出分析

### 🔄 三阶段连续评测（创新）
对同一任务连续执行三个阶段，全面评估模型能力：

1. **任务分解** - 将用户问题分解为子任务
2. **任务规划** - 规划子任务的执行顺序和依赖关系
3. **任务执行** - 按照规划执行任务并验证结果

**核心特点**:
- ✅ 评测模型在每个阶段的实际输出
- ✅ 使用ground_truth传递给下一阶段，保证上下文稳定
- ✅ 避免错误信息的连锁传播，独立评估每个阶段能力

## 快速开始

### 1. 环境配置

```bash
# 安装依赖
pip install -r requirements.txt

# 配置API密钥
cp .env.example .env
# 编辑 .env 文件，填入API密钥
```

### 2. 使用统一入口（推荐）

`run.py` 提供了更简洁的命令行接口：

```bash
# 传统评测
python run.py traditional [options]
python run.py traditional --task-type fix_bug

# 阶段独立评测
python run.py stage [options]
python run.py stage --stages decomposition planning

# 三阶段连续评测（逐个处理模式）
python run.py three-stage [options]
python run.py three-stage --test-id test_001  # 运行单个测试用例

# 三阶段连续评测（批量处理模式 - 更快）
python run.py three-stage --batch  # 运行所有6个测试用例
python run.py three-stage --batch --test-id test_002  # 批量模式运行单个用例
```

### 3. 直接调用脚本（可选）

你也可以直接运行各个脚本：

```bash
# 传统评测
python bin/run_evaluation.py
python bin/run_evaluation.py --task-type fix_bug

# 三阶段连续评测 - 逐个处理模式（默认）
python bin/run_three_stage_continuous.py  # 运行所有6个测试用例
python bin/run_three_stage_continuous.py --test-id test_001  # 运行单个测试用例

# 三阶段连续评测 - 批量处理模式
python bin/run_three_stage_continuous.py --batch  # 批量处理所有6个测试用例
# 批量模式：先批量处理所有用例的阶段1，再处理阶段2，最后处理阶段3
# 优点：执行速度更快，便于对比同一阶段的所有结果

# 阶段独立评测
python bin/run_stage_evaluation.py --stages decomposition
python bin/run_stage_evaluation.py --stages decomposition planning
```

### 📊 三阶段连续评测的两种模式

系统包含6个测试用例，覆盖所有任务类型：
- test_001: Bug修复任务 (fix_bug)
- test_002: 代码转换任务 (convert)
- test_003: 代码重构任务 (refactor)
- test_004: 环境配置任务 (env)
- test_005: 文档生成任务 (sum)
- test_006: 函数拆分任务 (split)

#### 逐个处理模式（默认）
```bash
python bin/run_three_stage_continuous.py  # 运行所有6个测试用例
```
- ✅ 每个测试用例连续完成三个阶段
- ✅ 便于跟踪单个用例的完整流程
- ✅ 实时看到每个用例的端到端结果
- 适合：调试单个用例、详细分析流程

**执行流程**：
```
测试用例1: 分解 → 规划 → 执行
测试用例2: 分解 → 规划 → 执行
...
测试用例6: 分解 → 规划 → 执行
```

#### 批量处理模式
```bash
python bin/run_three_stage_continuous.py --batch  # 批量处理所有6个测试用例
```
- ✅ 按阶段批量处理所有测试用例
- ✅ 执行速度更快
- ✅ 便于对比同一阶段的所有结果
- 适合：快速评测多个用例、批量实验

**执行流程**：
```
阶段1: 批量处理所有6个用例的分解阶段
阶段2: 批量处理所有6个用例的规划阶段
阶段3: 批量处理所有6个用例的执行阶段
```

#### 控制输出详细程度
```bash
# 默认：简洁输出（推荐）
python run.py three-stage

# 显示详细信息（模型输出、代码内容等）
python run.py three-stage --show-details
```

**注意**：
- 默认情况下不显示大量的中间输出，避免刷屏
- 所有详细信息都保存在日志文件中（`logs/evaluation.log`）
- 使用 `--show-details` 查看模型的详细输出
- 两种模式的逻辑完全一致，每个测试用例都会完整经过三个阶段，且使用ground_truth进行阶段间的上下文传递。

## 目录结构

```
docker_build_refactored/
├── run.py                        # 🚀 统一入口脚本（推荐）
├── bin/                          # 可执行脚本
│   ├── run_evaluation.py         # 传统单阶段评测入口
│   ├── run_stage_evaluation.py   # 阶段独立评测入口
│   └── run_three_stage_continuous.py  # 三阶段连续评测入口
├── config/
│   └── config.yaml               # 系统配置文件
├── data/
│   ├── prompts/                  # 提示词模板
│   │   ├── system_prompt_2.json  # 三阶段提示词
│   │   └── tool_list.json        # 工具定义
│   ├── tasks/                    # 任务数据
│   │   ├── bug_code/             # Bug修复任务
│   │   ├── code_convert/         # 代码转换任务
│   │   ├── code_refactor/        # 代码重构任务
│   │   ├── code_split/           # 代码拆分任务
│   │   └── code_sum/             # 代码摘要任务
│   ├── test_cases/               # 测试用例
│   │   └── exe_task_total.json   # 执行阶段测试用例
│   ├── stage_test_cases.json     # 阶段独立测试用例
│   └── three_stage_test_cases.json  # 三阶段连续测试用例
├── lib/
│   ├── api/                      # API客户端
│   │   ├── client.py             # 主模型客户端
│   │   └── judge_client.py       # 评估模型客户端
│   ├── core/                     # 核心功能
│   │   ├── config_manager.py     # 配置管理
│   │   ├── evaluation_engine.py  # 评测引擎
│   │   ├── logger.py             # 日志系统
│   │   ├── simple_data_manager.py # 数据备份恢复
│   │   └── utils.py              # 工具函数
│   ├── tools/                    # 工具执行器
│   │   └── tool_executor.py      # 工具调用执行
│   └── validators/               # 验证器
│       ├── bugcode.py            # Bug修复验证
│       ├── convert.py            # 代码转换验证
│       ├── refactor.py           # 代码重构验证
│       ├── split.py              # 代码拆分验证
│       ├── summary.py            # 代码摘要验证
│       ├── task_decomposition.py # 任务分解验证
│       └── task_planning.py      # 任务规划验证
├── docs/                         # 文档
│   ├── CONFIGURATION.md          # 配置指南
│   ├── QUICK_START.md            # 快速开始
│   ├── METRICS.md                # 评测指标说明
│   ├── THREE_STAGE_DESIGN.md     # 三阶段设计文档
│   ├── THREE_STAGE_SUMMARY.md    # 三阶段实现总结
│   ├── BATCH_VS_SEQUENTIAL.md    # 批量vs逐个处理对比
│   ├── CONTEXT_EXAMPLE.md        # 上下文构建示例
│   └── CONTEXT_OUTPUT_EXAMPLE.json # 输出示例
├── logs/                         # 日志输出目录
├── outputs/                      # 评测结果输出目录
├── scripts/                      # 工具脚本
│   ├── setup_conda_env.sh        # Conda环境设置
│   ├── backup_dataset.sh         # 数据备份
│   └── tests/                    # 测试脚本
└── tests/                        # 单元测试

```

## 配置说明

### 主配置文件 (`config/config.yaml`)

关键配置项：

```yaml
# API配置
api:
  base_url: "http://api.example.com/v1/chat/completions"
  default_model: "deepseek-v3.2"
  temperature: 0.7

# 三阶段评测配置
prompts:
  stages:
    decomposition:
      default_format: "markdown"  # json, markdown, xml

# 任务分解评测配置
evaluation:
  task_decomposition:
    use_llm_similarity: true      # 使用LLM判断语义相似度
    similarity_threshold: 0.7     # 相似度阈值
  
  # Judge Model配置（用于评估）
  judge_model:
    enabled: true
    model: "deepseek-v3.2"
    temperature: 0.1
```

详细配置说明见 [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

## 📊 评测指标

系统提供完整的量化评测指标：

### 阶段1 - 任务分解
- **召回率 (Recall)**: 模型覆盖了多少ground truth任务
- **精确率 (Precision)**: 模型输出中有多少是有效任务
- **F1分数**: 召回率和精确率的调和平均

### 阶段2 - 任务规划
- **覆盖度 (Coverage)**: 计划包含了多少任务
- **顺序正确率 (Order Correctness)**: 依赖关系满足比例
- **层级效率 (Level Efficiency)**: 并行化程度评估

### 阶段3 - 任务执行
- **任务通过率**: 验证器检查是否通过
- **执行轮次**: 完成任务的对话轮数
- **工具调用统计**: 工具使用次数和类型

### 整体汇总
- **各阶段通过率**: 每个阶段的测试用例通过比例
- **平均得分**: 各阶段的平均综合得分
- **完整流程通过率**: 三个阶段全部通过的测试用例比例

**详细指标说明见 [docs/METRICS.md](docs/METRICS.md)** 📈

## 三阶段评测原理

### 评测流程

```
用户问题
    ↓
[阶段1：任务分解]
    模型输出 → 评测（与ground_truth对比）
    ground_truth → 传递到阶段2
    ↓
[阶段2：任务规划]
    输入：ground_truth tasks
    模型输出 → 评测（检查依赖和顺序）
    ground_truth plan → 传递到阶段3
    ↓
[阶段3：任务执行]
    输入：ground_truth plan + task_data
    模型输出 → 评测（验证最终结果）
```

### 为什么使用ground_truth传递？

**核心原则**: 评测模型输出，但传递ground_truth给下一阶段

**优势**:
- ✅ 每个阶段独立评估，不受前序阶段影响
- ✅ 避免错误信息的连锁传播
- ✅ 保证评测的完整性和一致性
- ✅ 可以清晰看到每个阶段的能力边界

详细设计见 [docs/THREE_STAGE_DESIGN.md](docs/THREE_STAGE_DESIGN.md)

## 支持的任务类型

| 任务类型 | 说明 | 验证方式 |
|---------|------|---------|
| fix_bug | Bug修复 | 测试用例执行 |
| convert | 代码转换 | AST对比 + 测试执行 |
| refactor | 代码重构 | 函数签名验证 |
| env | 环境配置 | 依赖安装验证 |
| sum | 代码摘要 | LLM Judge评估 |
| split | 代码拆分 | LLM Judge评估 |

## 评测指标

### 传统评测指标
- **通过率**: 任务成功完成的比例
- **工具调用统计**: 每种工具的调用次数
- **对话轮次**: 完成任务所需的轮数
- **输出字符数**: 模型输出的总字符数

### 三阶段评测指标

**任务分解**:
- 召回率 (Recall): 标准答案中的任务有多少被召回
- 准确率 (Precision): 模型输出的任务中有多少是正确的
- F1分数: 综合指标

**任务规划**:
- 覆盖度 (Coverage): 规划覆盖了多少任务
- 顺序正确率 (Order Correctness): 依赖关系的正确性
- 层级效率 (Level Efficiency): 并行化程度

**任务执行**:
- 通过率: 最终执行结果的正确性
- 执行效率: 完成任务的轮次和工具调用

## 输出结果

### 传统评测输出

```json
{
  "total": 6,
  "passed": 5,
  "failed": 1,
  "pass_rate": 0.833,
  "results": [
    {
      "task_name": "bug_code_1",
      "task_type": "fix_bug",
      "passed": true,
      "metrics": {
        "total_rounds": 8,
        "tool_calls": 15,
        "tool_types": {"read_file": 5, "write_to_file": 3, ...}
      }
    }
  ]
}
```

### 三阶段评测输出

```json
{
  "test_case_id": "test_001",
  "stages": {
    "decomposition": {
      "model_output": {...},
      "evaluation": {"recall": 0.73, "precision": 1.0, "f1_score": 0.85},
      "passed": true
    },
    "planning": {
      "model_output": {...},
      "evaluation": {"coverage": 1.0, "order_correctness": 0.9},
      "passed": true
    },
    "execution": {
      "evaluation": {"passed": true, "pass_rate": 1.0},
      "passed": true
    }
  },
  "overall": {
    "all_stages_passed": true,
    "average_score": 0.88
  }
}
```

完整输出示例见 [docs/CONTEXT_OUTPUT_EXAMPLE.json](docs/CONTEXT_OUTPUT_EXAMPLE.json)

## 开发和测试

### 运行测试

```bash
# 运行单元测试
pytest tests/

# 运行特定测试
pytest tests/test_api_client.py

# 运行集成测试
python scripts/tests/test_validators.py
```

### 数据备份与恢复

评测过程中会自动备份和恢复任务数据：

```bash
# 手动备份
bash scripts/backup_dataset.sh

# 手动恢复
bash scripts/restore_dataset.sh
```

## 常见问题

### 1. API限流问题

如果遇到 `HTTP 429` 错误：
- 检查API配置的并发限制
- 系统已实现自动降级机制
- 批量判断时会自动处理限流

### 2. 格式提取失败

如果任务提取失败：
- 检查 `logs/__main__.log` 查看详细错误
- 确认模型输出格式符合配置（json/markdown/xml）
- 系统会自动尝试多种解析方法

### 3. 相似度判断不准确

调整相似度阈值：
```yaml
evaluation:
  task_decomposition:
    similarity_threshold: 0.7  # 降低或提高此值
```

**版本**: v2.0  
**更新日期**: 2025-12-10
