# 题目：带障碍的矩阵中的最大金币收集
# 
# 描述：
# 给你一个 m x n 的矩阵 grid，其中每个单元格可能是：
# - 0 表示空单元格
# - 1 表示这个单元格有一个金币
# - 2 表示这个单元格是一个障碍物
# 
# 你从左上角(0, 0)出发，目标是到达右下角(m-1, n-1)。
# 在每一步中，你可以向右或向下移动一格。
# 如果你经过一个有金币的单元格，你可以收集这个金币（每个金币只能被收集一次）。
# 你不能进入有障碍物的单元格。
# 
# 你有一个特殊的"穿墙技能"，可以使用至多k次，每次可以穿过一个障碍物单元格（穿过后障碍物仍然存在）。
# 
# 请找出你能收集的最大金币数量。
# 
# 输入：
# 第一行包含三个整数 m、n 和 k，表示矩阵的行数、列数和可使用的穿墙技能次数
# 接下来的 m 行，每行包含 n 个整数（0、1或2），表示矩阵的内容
# 
# 输出：
# 一个整数，表示能收集的最大金币数量
# 
# 约束：
# 1 <= m, n <= 100
# 0 <= k <= 10
# grid[i][j] 为 0、1 或 2

import sys

def max_coins(grid, k):
    m, n = len(grid), len(grid[0])
    
    dp = [[[-1 for _ in range(k+1)] for _ in range(n)] for _ in range(m)]
    
    def dfs(i, j, remain_k):
        if i >= m or j >= n:
            return float('-inf')
        
        if grid[i][j] == 2 and remain_k == 0:
            return float('-inf')
        
        if i == m-1 and j == n-1:
            return 1 if grid[i][j] == 1 else 0
        
        if dp[i][j][remain_k] != -1:
            return dp[i][j][remain_k]
        
        coin = 1 if grid[i][j] == 1 else 0
        
        skill_used = 1 if grid[i][j] == 2 else 0
        
        right = dfs(i, j+1, remain_k - skill_used)
        down = dfs(i+1, j, remain_k - skill_used)
        
        dp[i][j][remain_k] = coin + max(right, down)
        return dp[i][j][remain_k]
    
    result = dfs(0, 0, k)
    return max(0, result)

def process_test_cases(file_path):
    results = []
    
    with open(file_path, 'r') as file:
        lines = file.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            m, n, k = map(int, line.split())
            grid = []
            
            for j in range(i+1, i+1+m):
                if j < len(lines):
                    row = list(map(int, lines[j].strip().split()))
                    grid.append(row)
            
            result = max_coins(grid, k)
            results.append(result)
            
            i = i + 1 + m
    
    return results

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py input_file.txt")
        return
    
    file_path = sys.argv[1]
    results = process_test_cases(file_path)
    
    # 输出结果
    for i, result in enumerate(results):
        print(f"Test case {i+1}: {result}")

if __name__ == "__main__":
    main()
