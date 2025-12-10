# 数据集说明

## 目录结构

```
data/
├── tasks/                # 任务数据（评测时使用和修改）
│   ├── bug_code/         # Bug代码
│   ├── code_convert/     # 待转换代码
│   ├── code_refactor/    # 待重构代码
│   ├── code_env/         # 环境配置任务
│   ├── code_sum/         # 待总结项目
│   └── code_split/       # 待拆分代码
│
├── test_cases/           # 测试用例配置（JSON格式）
│   ├── exe_task_code.json
│   ├── exe_task_convert.json
│   ├── exe_task_refactor.json
│   ├── exe_task_env.json
│   ├── exe_task_sum.json
│   └── exe_task_split.json
│
└── prompts/              # 系统提示词
    ├── system_prompt_2.json
    └── tool_list.json
```

## 自动备份恢复

`tasks/`目录中的文件会在评测时被修改（如refactor任务）。

系统会自动备份和恢复：
- 评测前：自动备份`tasks/`到`.tasks_backup/`
- 评测后：自动从备份恢复
- 用户无感知，完全自动化

### 手动恢复（如需要）

```python
from lib.core.simple_data_manager import get_simple_data_manager

manager = get_simple_data_manager()
with manager.auto_restore_tasks():
    # 运行评测
    pass
# 自动恢复
```

---

**最后更新**: 2025-12-10
