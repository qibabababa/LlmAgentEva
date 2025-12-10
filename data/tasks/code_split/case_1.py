import statistics, datetime

def giant_cleaner(fillna: str = '0'):
    """
    硬编码数据 -> 清洗 -> 直接打印
    :param fillna: 缺失值填充值（字符串）
    :return: list[list[str]] 清洗后的二维数据
    """
    header = ['id', 'num_height', 'num_weight', 'city']
    rows = [
        ['1', '170', '60', 'Shanghai'],
        ['2', '180', '',   'Beijing'],
        ['3', '',   '55',  'Guangzhou'],
        ['',  '',   '',    ''],          
        ['4', '175', '70', 'Shenzhen']
    ]

    # 1) 删除全空行
    cleaned = [r for r in rows if not all(cell.strip() == '' for cell in r)]

    # 2) 缺失值填充
    for r in cleaned:
        for i, cell in enumerate(r):
            if cell.strip() == '':
                r[i] = fillna

    # 3) 对 num_ 开头的列做 z-score $\frac{x-\mu}{\sigma}$，并保留 2 位小数
    num_cols = [i for i, h in enumerate(header) if h.startswith('num_')]
    for idx in num_cols:
        col_vals = [float(r[idx]) for r in cleaned]
        mean = statistics.mean(col_vals)
        stdev = statistics.stdev(col_vals) if len(col_vals) > 1 else 1.0
        for r in cleaned:
            r[idx] = f"{(float(r[idx]) - mean) / stdev:.2f}"

    # 4) 再次填充空值（保险）
    for r in cleaned:
        for i, cell in enumerate(r):
            if cell.strip() == '':
                r[i] = fillna

    # 5) 打印
    print(' | '.join(header))
    print('-' * 60)
    for row in cleaned:
        print(' | '.join(row))

    return cleaned


if __name__ == '__main__':
    giant_cleaner()
