#!/bin/bash
# 重置测试环境脚本
# 清空测试环境中模型安装的所有包，恢复到纯净状态

set -e

TEST_ENV_NAME=${1:-"eval_test_env"}

echo "================================================"
echo "  重置测试环境"
echo "================================================"
echo ""
echo "环境名称: $TEST_ENV_NAME"
echo ""

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "❌ 错误: 未找到conda命令"
    exit 1
fi

# 检查环境是否存在
if ! conda env list | grep -q "^${TEST_ENV_NAME} "; then
    echo "❌ 错误: 环境 '${TEST_ENV_NAME}' 不存在"
    echo "请先运行: bash scripts/setup_test_env.sh"
    exit 1
fi

echo "当前环境中的包："
eval "$(conda shell.bash hook)"
conda activate "$TEST_ENV_NAME"
pip list
echo ""

read -p "确认要重置此环境吗？这将卸载所有第三方包 (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "正在获取需要保留的基础包..."
# 获取Python标准库和pip（这些不应该被卸载）
BASE_PACKAGES="pip setuptools wheel"

echo "正在获取所有已安装的包..."
INSTALLED_PACKAGES=$(pip list --format=freeze | cut -d'=' -f1 | grep -v -E "^(pip|setuptools|wheel)$")

if [ -z "$INSTALLED_PACKAGES" ]; then
    echo "✅ 环境已经是纯净状态，无需重置"
    exit 0
fi

echo ""
echo "将要卸载的包："
echo "$INSTALLED_PACKAGES"
echo ""

read -p "确认卸载这些包？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "正在卸载第三方包..."
for package in $INSTALLED_PACKAGES; do
    echo "  卸载: $package"
    pip uninstall -y "$package" 2>/dev/null || echo "    跳过: $package"
done

echo ""
echo "正在清理pip缓存..."
pip cache purge 2>/dev/null || echo "缓存已清理"

echo ""
echo "================================================"
echo "✅ 测试环境重置完成！"
echo "================================================"
echo ""
echo "当前环境中的包："
pip list
echo ""
echo "下一步操作："
echo "  再次运行env任务测试："
echo "  python bin/run_evaluation.py --task-type env"
echo ""
