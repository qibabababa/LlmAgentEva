# 评测系统配置指南

## 概述

本文档介绍如何配置评测系统的各项参数，特别是三阶段评测的格式和相似度判断设置。

## 配置文件位置

- **主配置文件**: `config/config.yaml`
- **提示词配置**: `data/prompts/system_prompt_2.json`
- **环境变量**: `.env`

## 任务分解阶段配置

### 1. 输出格式配置

在 `config/config.yaml` 中配置默认输出格式：

```yaml
prompts:
  system_prompt_file: "data/prompts/system_prompt_2.json"
  
  stages:
    decomposition:
      default_format: "markdown"  # 默认格式: json, markdown, xml
      supported_formats:
        - json
        - markdown
        - xml
```

**支持的格式**：

#### JSON 格式
```json
{
  "goal": "修复代码bug",
  "tasks": [
    "分析代码逻辑",
    "检查边界条件",
    "修复错误",
    "测试验证"
  ]
}
```

#### Markdown 格式
```markdown
# 目标
修复代码bug

# 任务要素
- 分析代码逻辑
- 检查边界条件
- 修复错误
- 测试验证
```

#### XML 格式
```xml
<taskDecomposition>
  <goal>修复代码bug</goal>
  <tasks>
    <task>分析代码逻辑</task>
    <task>检查边界条件</task>
    <task>修复错误</task>
    <task>测试验证</task>
  </tasks>
</taskDecomposition>
```

### 2. 相似度判断配置

在 `config/config.yaml` 中配置语义相似度判断：

```yaml
evaluation:
  task_decomposition:
    use_llm_similarity: true  # 是否使用LLM判断语义相似度
    similarity_threshold: 0.7  # 相似度阈值（LLM判断时推荐0.7）
    fallback_threshold: 0.5    # 降级到规则方法时的阈值
```

**配置说明**：

- **use_llm_similarity**: 
  - `true`: 使用LLM Judge批量判断语义相似度（推荐，准确度高）
  - `false`: 使用基于规则的方法（序列匹配+关键词匹配）

- **similarity_threshold**:
  - LLM判断推荐 `0.7` - LLM判断更准确，可以使用较高阈值
  - 规则方法推荐 `0.4-0.5` - 规则方法需要较低阈值

- **fallback_threshold**:
  - 当LLM判断失败时，自动降级到规则方法使用的阈值

### 3. Judge Model 配置

LLM相似度判断使用独立的Judge Model：

```yaml
evaluation:
  judge_model:
    enabled: true
    model: "deepseek-v3.2"  # 评估模型名称
    temperature: 0.1        # 低温度保证评估稳定性
    timeout: 120            # 评估超时时间（秒）
    max_tokens: 400         # 评估响应最大token数
    max_retries: 2          # 评估失败重试次数
    fallback_to_rules: true # LLM失败时是否回退到规则评估
```

在 `.env` 文件中配置API密钥：

```bash
# Judge Model API配置（如果与主模型不同）
JUDGE_API_KEY=your-judge-api-key
JUDGE_API_BASE_URL=http://api.example.com/v1/chat/completions
JUDGE_MODEL=deepseek-v3.2
```

## 测试用例配置

### 指定输出格式

在测试用例JSON文件中，可以为每个用例指定格式：

```json
{
  "stage": "decomposition",
  "mode": "open",
  "format": "json",  // 可选: json, markdown, xml (覆盖默认值)
  "name": "测试用例名称",
  "user_question": "这个代码有bug，找出并修复",
  "ground_truth": [
    "分析代码逻辑",
    "检查边界条件",
    "修复错误",
    "测试验证"
  ]
}
```

### 指定评测模式

- **open** (开放模式): 模型自由分解任务
- **constrained** (全集模式): 从提供的任务集合中选择

```json
{
  "stage": "decomposition",
  "mode": "constrained",  // 全集模式
  "format": "markdown",
  "user_question": "从以下任务中选择3-5个...",
  "ground_truth": [...]
}
```

## 提示词模板配置

在 `data/prompts/system_prompt_2.json` 中配置提示词模板：

```json
{
  "task": {
    "task_decomposition": {
      "base": "开放模式的基础提示词...",
      "all_tasks": "全集模式的基础提示词...",
      "format": {
        "base": "\n输出格式要求：\n",
        "json": "{ \"goal\": \"{goal}\", \"tasks\": [...] }",
        "markdown": "# 目标\n{goal}\n\n# 任务要素\n- task1\n- task2",
        "xml": "<taskDecomposition>...</taskDecomposition>"
      },
      "format_all": {
        "base": "\n输出格式要求：\n",
        "json": "...",
        "markdown": "...",
        "xml": "..."
      }
    }
  }
}
```

**说明**：

- `format`: 开放模式使用的格式模板
- `format_all`: 全集模式使用的格式模板（当前与format相同）

## 运行评测

### 使用默认配置

```bash
python bin/run_stage_evaluation.py --stages decomposition
```

### 指定格式（通过测试用例文件）

```bash
python bin/run_stage_evaluation.py \
  --stages decomposition \
  --test-file data/test_cases/custom_test.json
```

## 常见问题

### Q: 如何切换输出格式？

**A**: 有两种方式：

1. **全局修改**: 在 `config/config.yaml` 中修改 `prompts.stages.decomposition.default_format`
2. **测试用例修改**: 在测试用例JSON中添加 `"format": "json"` 字段

### Q: LLM相似度判断失败怎么办？

**A**: 系统会自动降级到基于规则的方法，使用 `fallback_threshold` 作为阈值。你可以：

1. 检查Judge Model的API配置是否正确
2. 检查是否遇到API限流（10次/分钟）
3. 查看日志文件了解具体错误原因

### Q: 如何调整相似度阈值？

**A**: 在 `config/config.yaml` 中修改：

```yaml
evaluation:
  task_decomposition:
    similarity_threshold: 0.7  # 调整此值
```

**建议值**：
- LLM判断: `0.7` (推荐)
- 规则方法: `0.4-0.5`

### Q: 如何验证格式提取是否正常？

**A**: 查看日志文件 `logs/__main__.log`，搜索：

```
提取到 X 个任务
```

如果提取失败，会有警告信息：

```
未能从响应中提取到任务列表
```

## 技术细节

### 格式自动检测

当 `format` 未指定或为 `"auto"` 时，系统会自动检测：

1. 如果包含 `"tasks"` 和 `{` → JSON
2. 如果包含 `<task` 和 `<tasks>` → XML  
3. 否则 → Markdown

### 任务提取逻辑

- **JSON**: 提取 `tasks` 数组中的所有元素
- **XML**: 提取所有 `<task>` 标签的文本内容
- **Markdown**: 提取以 `-`、`*`、`+`、`1.` 等开头的列表项

### 相似度计算

#### LLM方法（推荐）

```python
# 批量判断所有任务对
similarities = calculate_similarity_llm_batch(task_pairs)

# 返回 0.0-1.0 的分数
# 0.8-1.0: 高度相似
# 0.5-0.7: 部分相似  
# 0.0-0.3: 不相似
```

#### 规则方法（Fallback）

```python
similarity = seq_match * 0.6 + keyword_match * 0.4

# seq_match: 序列匹配度 (SequenceMatcher)
# keyword_match: 关键词匹配度 (Jaccard)
```

## 更新日志

### v2.0 (2025-12-10)

- ✅ 添加多格式支持（JSON, Markdown, XML）
- ✅ 实现LLM批量语义相似度判断
- ✅ 添加配置文件支持
- ✅ 改进任务提取算法
- ✅ 添加自动降级机制

---

**需要帮助？**

查看日志文件: `logs/__main__.log`  
提交问题: [项目Issue页面]
