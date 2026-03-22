#!/usr/bin/env python3

import sys
import requests
import logging
import os
from datetime import datetime


def setup_logging():
    # 脚本目录
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    SKILL_DIR = os.path.dirname(SCRIPT_DIR)

    # 日志目录改到技能内
    log_dir = os.path.join(SKILL_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"weatherquery_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            # logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)


def main(city: str) -> str:

    return '张传 yao 在'+city


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        city = sys.argv[1]
    else:
        city = '上海'
    logger = setup_logging()
    logger.info(f"参数: city={city}")
    data = main(city)
    print(data)
