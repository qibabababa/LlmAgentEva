#!/bin/bash
# 数据集恢复脚本
# 从备份恢复数据集

set -e

PROJECT_ROOT="/Users/jesseqi/docker_build_refactored"
DATA_DIR="$PROJECT_ROOT/data/tasks"
BACKUP_DIR="$PROJECT_ROOT/.backups"

echo "================================================"
echo "  数据集恢复工具"
echo "================================================"
echo ""

# 检查参数
if [ -z "$1" ]; then
    echo "用法: bash scripts/restore_dataset.sh <backup_name>"
    echo ""
    echo "可用的备份:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -1t "$BACKUP_DIR" | grep "^dataset_backup_" | nl
    else
        echo "  (无备份)"
    fi
    echo ""
    echo "恢复最新备份:"
    echo "  bash scripts/restore_dataset.sh latest"
    exit 1
fi

BACKUP_NAME="$1"

# 如果指定了latest，使用最新的备份
if [ "$BACKUP_NAME" = "latest" ]; then
    BACKUP_NAME=$(ls -1t "$BACKUP_DIR" | grep "^dataset_backup_" | head -1)
    if [ -z "$BACKUP_NAME" ]; then
        echo "❌ 错误: 没有找到任何备份"
        exit 1
    fi
    echo "使用最新备份: $BACKUP_NAME"
fi

BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

# 检查备份是否存在
if [ ! -d "$BACKUP_PATH" ]; then
    echo "❌ 错误: 备份不存在: $BACKUP_PATH"
    echo ""
    echo "可用的备份:"
    ls -1t "$BACKUP_DIR" | grep "^dataset_backup_" | nl
    exit 1
fi

echo "数据目录: $DATA_DIR"
echo "备份路径: $BACKUP_PATH"
echo ""

# 显示备份信息
if [ -f "$BACKUP_PATH/.backup_info" ]; then
    echo "备份信息:"
    cat "$BACKUP_PATH/.backup_info"
    echo ""
fi

# 警告：将会覆盖现有数据
echo "⚠️  警告: 这将会覆盖当前的数据目录！"
echo ""

# 询问是否继续
if [ "$2" != "--force" ] && [ "$2" != "-f" ]; then
    read -p "确认恢复？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

echo "开始恢复..."
echo ""

# 备份当前数据（以防万一）
if [ -d "$DATA_DIR" ]; then
    CURRENT_BACKUP="$BACKUP_DIR/dataset_before_restore_$(date +%Y%m%d_%H%M%S)"
    echo "备份当前数据到: $CURRENT_BACKUP"
    cp -r "$DATA_DIR" "$CURRENT_BACKUP"
fi

# 删除当前数据目录
echo "删除当前数据目录..."
rm -rf "$DATA_DIR"

# 恢复备份
echo "恢复备份数据..."
cp -r "$BACKUP_PATH" "$DATA_DIR"

# 删除备份信息文件（不需要在数据目录中）
rm -f "$DATA_DIR/.backup_info"

# 验证恢复
FILE_COUNT=$(find "$DATA_DIR" -type f | wc -l)
DIR_SIZE=$(du -sh "$DATA_DIR" | cut -f1)

echo ""
echo "================================================"
echo "✅ 恢复完成！"
echo "================================================"
echo ""
echo "恢复统计:"
echo "  文件数量: $FILE_COUNT"
echo "  目录大小: $DIR_SIZE"
echo ""
echo "验证恢复:"
echo "  ls -la $DATA_DIR"
echo ""
