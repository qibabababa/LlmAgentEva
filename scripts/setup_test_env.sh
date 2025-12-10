#!/bin/bash
# 创建纯净的测试环境脚本
# 用于测试模型配置环境的能力

set -e

TEST_ENV_NAME=${1:-"eval_test_env"}
PYTHON_VERSION=${2:-"3.10"}

echo "================================================"
echo "  创建纯净测试环境"
echo "================================================"
echo ""
echo "环境名称: $TEST_ENV_NAME"
echo "Python版本: $PYTHON_VERSION"
echo ""
echo "⚠️  重要说明："
echo "   这是一个纯净的测试环境，不会预装任何第三方库"
echo "   用于测试模型配置环境的能力（如安装opencv、numpy等）"
echo ""

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "❌ 错误: 未找到conda命令"
    echo "请先安装Anaconda或Miniconda"
    exit 1
fi

# 检查环境是否已存在
if conda env list | grep -q "^${TEST_ENV_NAME} "; then
    echo "⚠️  环境 '${TEST_ENV_NAME}' 已存在"
    read -p "是否删除并重新创建？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "正在删除旧环境..."
        conda env remove -n "$TEST_ENV_NAME" -y
    else
        echo "保留现有环境"
        exit 0
    fi
fi

# 创建纯净的conda环境（只安装Python，不安装任何第三方库）
echo "正在创建纯净的测试环境..."
conda create -n "$TEST_ENV_NAME" python="$PYTHON_VERSION" -y --no-default-packages

# 只安装pip（用于后续测试模型安装依赖）
echo "正在安装pip..."
eval "$(conda shell.bash hook)"
conda activate "$TEST_ENV_NAME"
python -m ensurepip --upgrade 2>/dev/null || echo "pip已存在"

echo ""
echo "================================================"
echo "✅ 纯净测试环境创建完成！"
echo "================================================"
echo ""
echo "环境信息："
echo "  Python版本: $(python --version)"
echo "  pip版本: $(pip --version)"
echo ""
echo "已安装的包："
pip list
echo ""
echo "下一步操作："
echo ""
echo "1. 配置.env文件（测试环境）："
echo "   CONDA_TEST_ENV_NAME=$TEST_ENV_NAME"
echo ""
echo "2. 激活环境测试："
echo "   conda activate $TEST_ENV_NAME"
echo "   python -c 'import sys; print(sys.executable)'"
echo ""
echo "3. 运行env任务测试模型配置能力："
echo "   python bin/run_evaluation.py --task-type env"
echo ""
echo "4. 重置环境（清空所有安装的包）："
echo "   bash scripts/reset_test_env.sh $TEST_ENV_NAME"
echo ""
echo "注意："
echo "  - 这是纯净环境，模型需要自己安装依赖（如opencv-python）"
echo "  - 不要在此环境中运行评测系统本身（会缺少依赖）"
echo "  - 仅用于测试env任务"
echo ""
