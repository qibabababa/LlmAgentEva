#!/bin/bash
# Conda环境快速设置脚本

set -e  # 遇到错误立即退出

CONDA_ENV_NAME=${1:-"eval_env"}
PYTHON_VERSION=${2:-"3.10"}

echo "================================================"
echo "  代码评测系统 - Conda环境设置脚本"
echo "================================================"
echo ""
echo "环境名称: $CONDA_ENV_NAME"
echo "Python版本: $PYTHON_VERSION"
echo ""

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "❌ 错误: 未找到conda命令"
    echo "请先安装Anaconda或Miniconda"
    echo "下载地址: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "✓ 检测到conda: $(conda --version)"
echo ""

# 检查环境是否已存在
if conda env list | grep -q "^${CONDA_ENV_NAME} "; then
    echo "⚠️  警告: 环境 '${CONDA_ENV_NAME}' 已存在"
    read -p "是否删除并重新创建？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "正在删除旧环境..."
        conda env remove -n "$CONDA_ENV_NAME" -y
    else
        echo "跳过环境创建，直接安装依赖..."
        conda activate "$CONDA_ENV_NAME"
        pip install -r requirements.txt
        pip install opencv-python numpy pandas requests beautifulsoup4 pillow scikit-learn
        echo ""
        echo "✅ 依赖安装完成！"
        exit 0
    fi
fi

# 创建conda环境
echo "正在创建conda环境..."
conda create -n "$CONDA_ENV_NAME" python="$PYTHON_VERSION" -y

# 激活环境
echo "正在激活环境..."
eval "$(conda shell.bash hook)"
conda activate "$CONDA_ENV_NAME"

# 安装项目依赖
echo ""
echo "正在安装项目依赖..."
pip install -r requirements.txt

# 安装常用第三方库（用于env任务）
echo ""
echo "正在安装常用第三方库..."
pip install opencv-python numpy pandas requests beautifulsoup4 pillow scikit-learn

echo ""
echo "================================================"
echo "✅ Conda环境设置完成！"
echo "================================================"
echo ""
echo "下一步操作："
echo ""
echo "1. 激活环境："
echo "   conda activate $CONDA_ENV_NAME"
echo ""
echo "2. 配置.env文件："
echo "   cp .env.example .env"
echo "   # 编辑.env，添加："
echo "   CONDA_ENV_NAME=$CONDA_ENV_NAME"
echo ""
echo "3. 运行评测："
echo "   python bin/run_evaluation.py"
echo ""
echo "4. 查看已安装的包："
echo "   conda list"
echo ""
echo "5. 停用环境："
echo "   conda deactivate"
echo ""
