import argparse
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal

import mysql.connector


def _json_default(obj):
    """处理 MySQL 返回的不可序列化类型"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _format_value(v) -> str:
    """将单个值转为适合表格展示的字符串"""
    if isinstance(obj := v, (datetime, date)):
        return obj.isoformat()
    if isinstance(v, float):
        # 去掉浮点尾部噪声，最多保留2位小数
        return f"{v:.2f}".rstrip('0').rstrip('.')
    if isinstance(v, Decimal):
        return f"{float(v):.2f}".rstrip('0').rstrip('.')
    if v is None:
        return "NULL"
    return str(v)


def _print_table(results: list):
    """用纯文本对齐打印查询结果表格"""
    if not results:
        return
    headers = list(results[0].keys())
    rows = [[_format_value(row[h]) for h in headers] for row in results]

    # 计算每列最大宽度（支持中文，按字符数估算）
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    def fmt_row(cells):
        return "|" + "|".join(f" {c:<{col_widths[i]}} " for i, c in enumerate(cells)) + "|"

    print(sep)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print(sep)




def connect_to_mysql(host, port, user, password, database):
    try:
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        if connection.is_connected():
            print("成功连接到 MySQL 数据库")
            return connection
    except Exception as e:
        print(f"连接 MySQL 数据库失败: {e}")
        return None



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MySQL 数据库查询工具')
    parser.add_argument('--sql', required=True, help='SQL 查询语句')
    parser.add_argument('--output', '-o', choices=['json', 'table', 'csv'], default='table', help='输出格式（默认 table）')
    parser.add_argument('--limit', '-l', type=int, help='限制返回数量')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')

    args = parser.parse_args()


    sr_host = os.getenv("SR_HOST")
    sr_port = os.getenv("SR_PORT")
    sr_user = os.getenv("SR_USER")
    sr_password = os.getenv("SR_PASSWORD")
    # 连接到 MySQL 数据库
    connection = connect_to_mysql(sr_host, sr_port, sr_user, sr_password, 'ads_pms')
    if connection is None:
        print('数据库连接失败，退出程序')
        sys.exit(1)

    query = args.sql
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query)
        # 判断查询类型
        if query.strip().upper().startswith('SELECT'):
            # SELECT 查询：获取所有结果
            results = cursor.fetchall()

            # 方法 1: 直接输出结果列表
            print(f"查询到 {len(results)} 条记录")

            fmt = args.output
            if fmt == 'table':
                _print_table(results)
            elif fmt == 'csv':
                import csv, io
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=list(results[0].keys()))
                writer.writeheader()
                for row in results:
                    writer.writerow({k: _format_value(v) for k, v in row.items()})
                print(buf.getvalue())
            else:
                print(json.dumps(results, indent=2, ensure_ascii=False, default=_json_default))
        else:
            # INSERT/UPDATE/DELETE 操作
            connection.commit()
            print(f"操作成功，影响行数：{cursor.rowcount}")

    except Exception as e:
        print(f'执行查询失败：{e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()
        print('数据库连接已关闭')
