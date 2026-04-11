#!/usr/bin/env python3
"""
客户管理工具
用法：
  python customer.py --list                        # 列出所有客户
  python customer.py --get C001                    # 查询单个客户
  python customer.py --followup                    # 今日需要跟进的客户
  python customer.py --search 蓝鲸                  # 搜索客户
"""

import argparse
import json
from datetime import datetime, timedelta

CUSTOMERS = {
    "C001": {
        "id": "C001",
        "name": "蓝鲸电商科技有限公司",
        "short_name": "蓝鲸电商",
        "contact": "王浩",
        "title": "采购总监",
        "phone": "138-0010-2233",
        "city": "上海",
        "type": "电商",
        "monthly_revenue": 250000,
        "contract_end": "2026-12-31",
        "discount": "8.5折",
        "rating": "A",
        "last_followup": "2026-04-01",
        "next_followup": "2026-04-08",
        "notes": "王总反映时效满意，询问是否有仓储服务，需跟进仓配一体化方案报价",
        "tags": ["核心客户", "电商", "仓配潜力"]
    },
    "C002": {
        "id": "C002",
        "name": "鑫达精密机械制造有限公司",
        "short_name": "鑫达制造",
        "contact": "李娜",
        "title": "物流主管",
        "phone": "139-8872-5566",
        "city": "苏州",
        "type": "制造业",
        "monthly_revenue": 80000,
        "contract_end": None,
        "discount": "9折",
        "rating": "B",
        "last_followup": "2026-03-28",
        "next_followup": "2026-04-09",
        "notes": "⚠️ 重要：对上月破损件赔偿结果不满意，需要安抚，准备赔偿方案",
        "tags": ["需安抚", "制造业", "保价需求"]
    },
    "C003": {
        "id": "C003",
        "name": "美好家居连锁有限公司",
        "short_name": "美好家居",
        "contact": "陈思远",
        "title": "运营总监",
        "phone": "186-5523-8899",
        "city": "广州",
        "type": "零售",
        "monthly_revenue": 0,
        "estimated_revenue": 175000,
        "contract_end": None,
        "discount": "待定",
        "rating": "B+",
        "last_followup": "2026-04-05",
        "next_followup": "2026-04-10",
        "notes": "已发送报价方案，等待回复。4月10日跟进是否收到，推进拜访",
        "tags": ["潜在客户", "家居大件", "竞品切换"]
    },
    "C004": {
        "id": "C004",
        "name": "顺和国际贸易有限公司",
        "short_name": "顺和贸易",
        "contact": "张明",
        "title": "总经理",
        "phone": "135-6688-0011",
        "city": "深圳",
        "type": "贸易",
        "monthly_revenue": 120000,
        "contract_end": "2026-06-30",
        "discount": "9折",
        "rating": "A-",
        "last_followup": "2026-03-15",
        "next_followup": "2026-04-15",
        "notes": "合同续签沟通顺利，期望价格维持。5月底发起续签，提前锁定",
        "tags": ["老客户", "贸易", "合同续签"]
    },
    "C005": {
        "id": "C005",
        "name": "博雅文化出版传媒集团",
        "short_name": "博雅出版",
        "contact": "刘芳",
        "title": "行政主管",
        "phone": "021-5512-3344",
        "city": "北京",
        "type": "出版",
        "monthly_revenue": 20000,
        "contract_end": None,
        "discount": "无",
        "rating": "C",
        "last_followup": "2026-02-20",
        "next_followup": "2026-04-20",
        "notes": "临时客户，季度问候，推荐签框架合同",
        "tags": ["小客户", "出版物"]
    }
}


def list_customers(rating_filter=None):
    """列出所有客户"""
    results = []
    for cid, c in CUSTOMERS.items():
        if rating_filter and c["rating"] != rating_filter:
            continue
        results.append({
            "id": cid,
            "short_name": c["short_name"],
            "contact": c["contact"],
            "phone": c["phone"],
            "rating": c["rating"],
            "next_followup": c["next_followup"],
            "monthly_revenue": c.get("monthly_revenue", 0),
            "notes_brief": c["notes"][:30] + "..." if len(c["notes"]) > 30 else c["notes"]
        })
    return sorted(results, key=lambda x: x["next_followup"])


def get_customer(customer_id):
    """获取客户详情"""
    return CUSTOMERS.get(customer_id.upper())


def get_followup_today(days_ahead=3):
    """获取需要跟进的客户（未来N天内）"""
    today = datetime.now().date()
    deadline = today + timedelta(days=days_ahead)
    results = []
    for cid, c in CUSTOMERS.items():
        if c["next_followup"]:
            followup_date = datetime.strptime(c["next_followup"], "%Y-%m-%d").date()
            if followup_date <= deadline:
                urgency = "🔴 今日" if followup_date <= today else "🟡 即将"
                results.append({
                    "urgency": urgency,
                    "id": cid,
                    "short_name": c["short_name"],
                    "contact": c["contact"],
                    "phone": c["phone"],
                    "followup_date": c["next_followup"],
                    "action": c["notes"]
                })
    return sorted(results, key=lambda x: x["followup_date"])


def search_customers(keyword):
    """搜索客户"""
    results = []
    kw = keyword.lower()
    for cid, c in CUSTOMERS.items():
        searchable = f"{c['name']}{c['short_name']}{c['contact']}{c['city']}{c['type']}".lower()
        if kw in searchable:
            results.append(c)
    return results


def main():
    parser = argparse.ArgumentParser(description="客户管理工具")
    parser.add_argument("--list", action="store_true", help="列出所有客户")
    parser.add_argument("--get", help="查询客户详情（客户ID）")
    parser.add_argument("--followup", action="store_true", help="查看需跟进客户")
    parser.add_argument("--search", help="搜索客户关键词")
    parser.add_argument("--days", type=int, default=3, help="跟进提前天数（默认3天）")

    args = parser.parse_args()

    if args.list:
        result = list_customers()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.get:
        result = get_customer(args.get)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": f"未找到客户 {args.get}"}, ensure_ascii=False))
    elif args.followup:
        result = get_followup_today(args.days)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.search:
        result = search_customers(args.search)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
