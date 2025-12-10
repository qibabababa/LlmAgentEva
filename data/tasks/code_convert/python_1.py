import sys


def main() -> None:
    line = sys.stdin.readline().strip()
    if not line:
        # 没有输入直接退出
        return

    try:
        a, b = map(int, line.split())
    except ValueError:
        print("Input must be two integers", file=sys.stderr)
        sys.exit(1)

    print(a // b)   
    print(a % b)    


if __name__ == "__main__":
    main()
