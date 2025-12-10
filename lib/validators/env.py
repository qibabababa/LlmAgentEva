import os
import sys
import subprocess
from pathlib import Path
from typing import Union, Sequence

# 默认虚拟环境目录（可通过环境变量覆盖）
DEFAULT_VENV_DIR = Path(os.getenv("VENV_PATH", "")).resolve() if os.getenv("VENV_PATH") else None


def _get_python_executable(venv_dir: Path = None, use_conda: bool = False, conda_env: str = None) -> Path:
    """
    获取Python可执行文件路径
    
    参数
    ----
    venv_dir : Path
        虚拟环境目录路径（venv/virtualenv方式）
    use_conda : bool
        是否使用conda环境
    conda_env : str
        conda环境名称
        
    返回
    ----
    Path
        Python可执行文件路径
    """
    if use_conda and conda_env:
        # 使用conda环境
        result = subprocess.run(
            ["conda", "info", "--envs"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if conda_env in line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 2:
                        env_path = Path(parts[-1])
                        python_exe = env_path / ("python.exe" if os.name == "nt" else "bin/python")
                        if python_exe.exists():
                            return python_exe.resolve()
        
        # 如果找不到，尝试使用conda run
        return Path("conda")  # 返回特殊标记
    
    if venv_dir:
        # 使用venv/virtualenv
        return (venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python").resolve()
    
    # 使用系统Python
    return Path(sys.executable).resolve()


def _venv_python(venv_dir: Path) -> Path:
    """
    根据平台返回虚拟环境里的 python 可执行文件路径
    （保留此函数以向后兼容）
    """
    return _get_python_executable(venv_dir=venv_dir)


def validate_env(
    env_file: Union[str, Path],
    venv_dir: Union[str, Path] | None = None,
    extra_args: Sequence[str] | None = None,
    use_conda: bool = False,
    conda_env: str = None,
    use_test_env: bool = True,  # 默认使用测试环境
) -> bool:
    """
    在指定虚拟环境中运行 `env_file`。

    参数
    ----
    env_file : str | Path
        要执行的 Python 文件路径
    venv_dir : str | Path | None
        虚拟环境目录；若 None 则使用 DEFAULT_VENV_DIR
    extra_args : 可选
        传给目标脚本的其他命令行实参，如 ["--debug", "foo"]
    use_conda : bool
        是否使用conda环境（默认False）
    conda_env : str | None
        conda环境名称（当use_conda=True时使用）
    use_test_env : bool
        是否使用测试环境（默认True）。测试环境是纯净的空白环境，
        用于测试模型配置依赖的能力。如果False，则使用开发环境。

    返回
    ----
    bool
        子进程退出码为 0 → True，否则 False
        
    示例
    ----
    # 使用测试环境（推荐，测试模型配置能力）
    validate_env("script.py", use_test_env=True)
    
    # 使用开发环境（不推荐，依赖可能已安装）
    validate_env("script.py", use_test_env=False)
    
    # 使用venv/virtualenv
    validate_env("script.py", venv_dir="/path/to/venv")
    
    # 使用conda环境
    validate_env("script.py", use_conda=True, conda_env="myenv")
    
    # 使用系统Python
    validate_env("script.py", use_test_env=False)
    """
    env_file = Path(env_file).resolve()
    if not env_file.exists():
        print(f"[validate_env] 文件不存在: {env_file}", file=sys.stderr)
        return False

    # 从环境变量读取配置
    if not use_conda and not venv_dir:
        # 根据use_test_env选择使用测试环境还是开发环境
        if use_test_env:
            # 优先使用测试环境
            conda_test_env = os.getenv("CONDA_TEST_ENV_NAME")
            venv_test_path = os.getenv("VENV_TEST_PATH")
            
            if conda_test_env:
                use_conda = True
                conda_env = conda_test_env
                print(f"[validate_env] 使用测试环境: conda '{conda_test_env}'")
            elif venv_test_path:
                venv_dir = venv_test_path
                print(f"[validate_env] 使用测试环境: venv '{venv_test_path}'")
            else:
                print(f"[validate_env] ⚠️  警告: 未配置测试环境，回退到开发环境")
                print(f"[validate_env] 建议运行: bash scripts/setup_test_env.sh")
                # 回退到开发环境
                use_test_env = False
        
        if not use_test_env:
            # 使用开发环境
            conda_env_name = os.getenv("CONDA_ENV_NAME")
            if conda_env_name:
                use_conda = True
                conda_env = conda_env_name
                print(f"[validate_env] 使用开发环境: conda '{conda_env_name}'")
            elif os.getenv("VENV_PATH"):
                venv_dir = os.getenv("VENV_PATH")
                print(f"[validate_env] 使用开发环境: venv '{venv_dir}'")
    
    # 获取Python可执行文件
    if use_conda and conda_env:
        # 使用conda环境
        cmd = ["conda", "run", "-n", conda_env, "python", str(env_file)]
        if extra_args:
            cmd.extend(map(str, extra_args))
        print(f"[validate_env] 执行命令: {' '.join(cmd)}")
    else:
        # 使用venv或系统Python
        venv_dir_path = Path(venv_dir).resolve() if venv_dir else DEFAULT_VENV_DIR
        if venv_dir_path:
            python_exe = _get_python_executable(venv_dir=venv_dir_path)
            if not python_exe.exists():
                print(f"[validate_env] 虚拟环境解释器不存在: {python_exe}", file=sys.stderr)
                return False
        else:
            python_exe = _get_python_executable()
            print(f"[validate_env] 使用当前Python: {python_exe}")
        
        cmd = [str(python_exe), str(env_file)]
        if extra_args:
            cmd.extend(map(str, extra_args))
        print("[validate_env] 执行命令:", " ".join(cmd))

    proc = subprocess.run(cmd)  # 继承父进程的 stdio，方便观察输出
    return proc.returncode == 0
