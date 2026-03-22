import argparse
import json
import os
import sys

import mysql.connector




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
    # parser.add_argument('--output', '-o', choices=['json', 'table', 'csv'], default='json', help='输出格式')
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
            print(json.dumps(results, indent=2, ensure_ascii=False))
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
