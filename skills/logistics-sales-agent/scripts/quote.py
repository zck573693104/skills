#!/usr/bin/env python3
"""
物流报价查询工具
用法：python quote.py --from 上海 --to 北京 --type ltl --weight 300
"""

import argparse
import json
import sys

# 模拟运价数据库
FREIGHT_RATES = {
    "ftl": {
        ("上海", "北京"): {"4.2米厢车": 3800, "9.6米厢车": 6500, "17.5米平板": 9800},
        ("上海", "广州"): {"4.2米厢车": 3200, "9.6米厢车": 5800, "17.5米平板": 8600},
        ("上海", "成都"): {"4.2米厢车": 4200, "9.6米厢车": 7200, "17.5米平板": 10500},
        ("北京", "广州"): {"4.2米厢车": 3500, "9.6米厢车": 6000},
        ("北京", "成都"): {"9.6米厢车": 6800},
        ("广州", "武汉"): {"4.2米厢车": 2800, "9.6米厢车": 5000},
        ("深圳", "北京"): {"9.6米厢车": 6200},
        ("深圳", "成都"): {"9.6米厢车": 7000},
    },
    "ltl": {
        ("上海", "北京"): {"0-100": 15, "100-500": 12, "500-1000": 10, "1000-3000": 8, "days": "3-4"},
        ("上海", "广州"): {"0-100": 12, "100-500": 10, "500-1000": 8.5, "1000-3000": 7, "days": "3-4"},
        ("上海", "成都"): {"0-100": 16, "100-500": 13, "500-1000": 11, "1000-3000": 9, "days": "4-5"},
        ("上海", "武汉"): {"0-100": 10, "100-500": 8, "500-1000": 7, "1000-3000": 6, "days": "2-3"},
        ("北京", "广州"): {"0-100": 14, "100-500": 11, "500-1000": 9, "1000-3000": 7.5, "days": "4-5"},
        ("广州", "上海"): {"0-100": 12, "100-500": 10, "500-1000": 8.5, "1000-3000": 7, "days": "3-4"},
        ("广州", "北京"): {"0-100": 14, "100-500": 11, "500-1000": 9, "1000-3000": 7.5, "days": "4-5"},
        ("成都", "上海"): {"0-100": 16, "100-500": 13, "500-1000": 11, "1000-3000": 9, "days": "4-5"},
    }
}

FTL_TRANSIT_DAYS = {
    ("上海", "北京"): 2, ("上海", "广州"): 2, ("上海", "成都"): 3,
    ("北京", "广州"): 3, ("北京", "成都"): 3, ("广州", "武汉"): 2,
    ("深圳", "北京"): 2, ("深圳", "成都"): 3,
}

SURCHARGES = {
    "fuel": 0.08,       # 燃油附加费 8%
    "oversized": 0.20,  # 超长附加费 20%
    "overweight": 0.15, # 超重附加费 15%
}

VOLUME_DISCOUNTS = [
    (500000, 0.80),
    (200000, 0.85),
    (100000, 0.90),
    (50000, 0.95),
    (0, 1.00),
]


def get_ltl_rate(origin, dest, weight_kg):
    """查询零担运价"""
    key = (origin, dest)
    if key not in FREIGHT_RATES["ltl"]:
        return None

    rates = FREIGHT_RATES["ltl"][key]
    if weight_kg <= 100:
        rate = rates["0-100"]
    elif weight_kg <= 500:
        rate = rates["100-500"]
    elif weight_kg <= 1000:
        rate = rates["500-1000"]
    elif weight_kg <= 3000:
        rate = rates["1000-3000"]
    else:
        return {"error": "零担最大承运3吨，超出请使用整车"}

    base_cost = weight_kg * rate
    fuel_surcharge = base_cost * SURCHARGES["fuel"]
    total = base_cost + fuel_surcharge

    return {
        "type": "零担(LTL)",
        "origin": origin,
        "destination": dest,
        "weight": f"{weight_kg}kg",
        "unit_rate": f"{rate}元/kg",
        "base_cost": round(base_cost, 2),
        "fuel_surcharge": round(fuel_surcharge, 2),
        "total": round(total, 2),
        "transit_days": rates["days"],
        "note": "以上为标准价，大客户可申请折扣"
    }


def get_ftl_rates(origin, dest):
    """查询整车运价"""
    key = (origin, dest)
    if key not in FREIGHT_RATES["ftl"]:
        return None

    rates = FREIGHT_RATES["ftl"][key]
    days = FTL_TRANSIT_DAYS.get(key, "3-5")
    results = []

    for vehicle_type, base_price in rates.items():
        fuel_surcharge = round(base_price * SURCHARGES["fuel"], 0)
        total = base_price + fuel_surcharge
        results.append({
            "vehicle_type": vehicle_type,
            "base_price": base_price,
            "fuel_surcharge": int(fuel_surcharge),
            "total": int(total),
        })

    return {
        "type": "整车(FTL)",
        "origin": origin,
        "destination": dest,
        "transit_days": days,
        "options": results,
        "note": "整车含燃油附加费，大客户折扣另议"
    }


def calc_discount(monthly_volume):
    """计算大客户折扣"""
    for threshold, discount in VOLUME_DISCOUNTS:
        if monthly_volume >= threshold:
            return discount
    return 1.0


def main():
    parser = argparse.ArgumentParser(description="物流报价查询工具")
    parser.add_argument("--from", dest="origin", required=True, help="出发城市")
    parser.add_argument("--to", dest="dest", required=True, help="目的城市")
    parser.add_argument("--type", choices=["ltl", "ftl", "both"], default="both", help="运输类型")
    parser.add_argument("--weight", type=float, default=0, help="货物重量(kg)，零担必填")
    parser.add_argument("--monthly-volume", type=float, default=0, help="月均运费(元)，用于计算折扣")

    args = parser.parse_args()
    result = {"query": {"origin": args.origin, "dest": args.dest}}

    if args.type in ("ltl", "both") and args.weight > 0:
        ltl = get_ltl_rate(args.origin, args.dest, args.weight)
        if ltl:
            if args.monthly_volume > 0:
                discount = calc_discount(args.monthly_volume)
                if discount < 1.0:
                    ltl["discount"] = f"{int(discount*10)}折"
                    ltl["discounted_total"] = round(ltl["total"] * discount, 2)
            result["ltl_quote"] = ltl
        else:
            result["ltl_quote"] = {"error": f"暂无 {args.origin}→{args.dest} 零担线路，请联系商务"}

    if args.type in ("ftl", "both"):
        ftl = get_ftl_rates(args.origin, args.dest)
        if ftl:
            if args.monthly_volume > 0:
                discount = calc_discount(args.monthly_volume)
                if discount < 1.0:
                    ftl["discount"] = f"{int(discount*10)}折"
                    for opt in ftl["options"]:
                        opt["discounted_total"] = int(opt["total"] * discount)
            result["ftl_quote"] = ftl
        else:
            result["ftl_quote"] = {"error": f"暂无 {args.origin}→{args.dest} 整车线路，请联系商务"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
