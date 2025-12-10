#!/bin/bash
# 数据集备份脚本
# 在评测前备份原始数据集

set -e

PROJECT_ROOT="/Users/jesseqi/docker_build_refactored"
DATA_DIR="$PROJECT_ROOT/data/tasks"
BACKUP_DIR="$PROJECT_ROOT/.backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="dataset_backup_$TIMESTAMP"

echo "================================================"
echo "  数据集备份工具"
echo "================================================"
echo ""

# 检查数据目录是否存在
if [ ! -d "$DATA_DIR" ]; then
    echo "❌ 错误: 数据目录不存在: $DATA_DIR"
    exit 1
fi

# 创建备份目录
mkdir -p "$BACKUP_DIR"

echo "数据目录: $DATA_DIR"
echo "备份目录: $BACKUP_DIR"
echo "备份名称: $BACKUP_NAME"
echo ""

# 计算数据集大小
DATA_SIZE=$(du -sh "$DATA_DIR" | cut -f1)
echo "数据集大小: $DATA_SIZE"
echo ""

# 询问是否继续
if [ "$1" != "--force" ] && [ "$1" != "-f" ]; then
    read -p "确认备份？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

echo "开始备份..."
echo ""

# 创建备份
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
cp -r "$DATA_DIR" "$BACKUP_PATH"

# 计算备份大小
BACKUP_SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)

# 生成备份信息文件
cat > "$BACKUP_PATH/.backup_info" << EOF
备份时间: $(date '+%Y-%m-%d %H:%M:%S')
数据目录: $DATA_DIR
备份大小: $BACKUP_SIZE
文件数量: $(find "$BACKUP_PATH" -type f | wc -l)
Git提交: $(cd "$PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "N/A")
EOF

echo "================================================"
echo "✅ 备份完成！"
echo "================================================"
echo ""
echo "备份信息:"
cat "$BACKUP_PATH/.backup_info"
echo ""
echo "备份路径: $BACKUP_PATH"
echo ""
echo "恢复命令:"
echo "  bash scripts/restore_dataset.sh $BACKUP_NAME"
echo ""
echo "删除备份:"
echo "  rm -rf $BACKUP_PATH"
echo ""

# 清理旧备份（保留最近10个）
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR" | grep "^dataset_backup_" | wc -l)
if [ "$BACKUP_COUNT" -gt 10 ]; then
    echo "清理旧备份（保留最近10个）..."
    ls -1t "$BACKUP_DIR" | grep "^dataset_backup_" | tail -n +11 | while read old_backup; do
        echo "  删除: $old_backup"
        rm -rf "$BACKUP_DIR/$old_backup"
    done
    echo ""
fi

echo "当前所有备份:"
ls -1t "$BACKUP_DIR" | grep "^dataset_backup_"
echo ""
