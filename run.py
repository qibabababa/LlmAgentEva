#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path


def print_banner():
    print("\n" + "="*70)
    print("              AI代码评测系统 v2.0")
    print("="*70)
    print("\n可用的评测模式：")
    print("  1. traditional    - 传统单阶段评测（6种任务类型）")
    print("  2. stage          - 阶段独立评测（分解、规划、执行）")
    print("  3. three-stage    - 三阶段连续评测（完整流程）")
    print("\n示例:")
    print("  python run.py traditional --task-type fix_bug")
    print("  python run.py stage --stages decomposition")
    print("  python run.py three-stage --test-id test_001")
    print("  python run.py three-stage --batch              # 批量处理模式")
    print("\n详细帮助:")
    print("  python run.py traditional --help")
    print("  python run.py stage --help")
    print("  python run.py three-stage --help")
    print("="*70 + "\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        print_banner()
        return 0
    
    mode = sys.argv[1]
    args = sys.argv[2:]
    
    bin_dir = Path(__file__).parent / "bin"
    
    if mode == "traditional":
        script = bin_dir / "run_evaluation.py"
    elif mode == "stage":
        script = bin_dir / "run_stage_evaluation.py"
    elif mode == "three-stage":
        script = bin_dir / "run_three_stage_continuous.py"
    else:
        print(f"❌ 未知的评测模式: {mode}")
        print("   可用模式: traditional, stage, three-stage")
        print("   运行 'python run.py --help' 查看帮助")
        return 1
    
    if not script.exists():
        print(f"❌ 脚本不存在: {script}")
        return 1
    
    # 执行对应的脚本
    cmd = [sys.executable, str(script)] + args
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
