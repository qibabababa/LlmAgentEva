# 快速开始

## 1. 安装

```bash
pip install -r requirements.txt
```

## 2. 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置，添加API密钥
vim .env
```

必填项：
```bash
API_KEY=your-api-key
API_BASE_URL=your-api-url
API_MODEL=your-model-name
```

## 3. 运行评测

### 传统评测

```bash
# 评测所有任务
python bin/run_evaluation.py

# 评测特定任务
python bin/run_evaluation.py --task-type fix_bug
```

### 三阶段评测

```bash
# 交互式评测
python bin/run_stage_evaluation.py

# 评测全流程
python bin/run_stage_evaluation.py --stages all
```

## 4. 查看结果

```bash
# 评测结果
ls outputs/

# 查看日志
tail -f logs/__main__.log
```

## 支持的任务类型

- `fix_bug` - Bug修复
- `convert` - 代码转换
- `refactor` - 代码重构
- `env` - 环境配置
- `sum` - 代码总结
- `split` - 代码拆分

## 常见问题

**Q: 如何查看详细日志？**
```bash
tail -f logs/__main__.log
```

**Q: 测试数据会被修改吗？**  
A: 会，但评测系统会自动恢复，无需担心。

**Q: 如何手动恢复测试数据？**
```python
from lib.core.test_data_manager import get_test_data_manager
get_test_data_manager().restore_all()
```

---

更多详细配置请查看主项目 [README.md](../README.md)
